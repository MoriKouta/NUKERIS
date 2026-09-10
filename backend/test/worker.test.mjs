import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker,{VERSION,RULESET,signRun,verifyRun,validResult,submitResult,tokenHash} from '../src/worker.mjs';

function environment() {
  const sqlite=new DatabaseSync(':memory:');
  sqlite.exec(readFileSync(new URL('../migrations/0001_rankings.sql',import.meta.url),'utf8'));
  const wrap=(sql,args=[])=>({
    bind(...values){return wrap(sql,values);},
    async first(){return sqlite.prepare(sql).get(...args)||null;},
    async all(){return {results:sqlite.prepare(sql).all(...args)};},
    async run(){return {meta:sqlite.prepare(sql).run(...args)};},
    execute(){return sqlite.prepare(sql).run(...args);}
  });
  return {sqlite,DB:{prepare:wrap,async batch(statements){
    sqlite.exec('BEGIN');try{const result=statements.map(s=>s.execute());sqlite.exec('COMMIT');return result;}
    catch(e){sqlite.exec('ROLLBACK');throw e;}
  }},RUN_SIGNING_KEY:'local-test-fixture-not-a-production-secret',
  REQUEST_LIMITER:{async limit(){return {success:true};}},REGISTER_LIMITER:{async limit(){return {success:true};}}};
}
function request(path,body,token,method='POST') {
  return new Request('https://ranking.example.com'+path,{method,
    headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
}
const profile={nickname:'MORI',country:'JP',region:'SAITAMA'};
async function register(env,p=profile) {
  const r=await worker.fetch(request('/v1/players',{profile:p,version:VERSION}),env);
  assert.equal(r.status,201);return r.json();
}
const result=(overrides={})=>({mode:'score_attack_120',ruleset:RULESET,version:VERSION,
  score:500,time_ms:120000,lines:4,pieces:100,...overrides});
async function runToken(env,id,mode='score_attack_120',now=1000000) {
  const run={id:crypto.randomUUID(),player_id:id,mode,ruleset:RULESET,version:VERSION,
    issued_ms:now-120000,expires_ms:now+15000,seed:'0123456789abcdef'};
  await env.DB.prepare('INSERT INTO runs(id,player_id,mode,ruleset,issued_ms,expires_ms) VALUES(?,?,?,?,?,?)')
    .bind(run.id,id,mode,RULESET,run.issued_ms,run.expires_ms).run();
  return signRun(run,env.RUN_SIGNING_KEY);
}

test('server credentials are random and only hashes are stored',async()=>{
  const e=environment();const p=await register(e);
  assert.match(p.player_token,/^[a-f0-9]{64}$/);
  const stored=e.sqlite.prepare('SELECT * FROM players').get();
  assert.equal(stored.token_hash,await tokenHash(p.player_token));
  assert.notEqual(stored.token_hash,p.player_token);
  assert.deepEqual(Object.keys(stored).sort(),['country','id','nickname','region','token_hash']);
});
test('signed tokens reject tampering and expiration',async()=>{
  const e=environment();const token=await signRun({issued_ms:1,expires_ms:100},e.RUN_SIGNING_KEY);
  assert.equal((await verifyRun(token,e.RUN_SIGNING_KEY,50)).expires_ms,100);
  await assert.rejects(verifyRun(token,e.RUN_SIGNING_KEY,101));
  await assert.rejects(verifyRun(token.slice(0,-3)+'AAA',e.RUN_SIGNING_KEY,50));
});
test('result sanity, versions and rulesets are strict',()=>{
  assert.equal(validResult(result()),true);
  for(const bad of [{score:-1},{time_ms:120001},{pieces:Infinity},{ruleset:'ruleset_2'},
    {version:'9.9.9'},{mode:'normal'},{hostname:'private'},{lines:9999},{score:true}]) {
    assert.equal(validResult(result(bad)),false);
  }
});
test('atomic duplicate rejection and PB cannot regress',async()=>{
  const e=environment();const p=await register(e);const player={id:p.player_id};
  const token=await runToken(e,player.id);
  await submitResult(e,player,token,result(),1000000);
  await assert.rejects(submitResult(e,player,token,result({score:1000}),1000000),{status:409});
  await submitResult(e,player,await runToken(e,player.id),result({score:100}),1000000);
  assert.equal(e.sqlite.prepare('SELECT score FROM personal_bests').get().score,500);
  assert.equal(e.sqlite.prepare('SELECT COUNT(*) AS n FROM submissions').get().n,2);
});
test('concurrent duplicate batches write once',async()=>{
  const e=environment();const p=await register(e);const player={id:p.player_id};const token=await runToken(e,player.id);
  const outcomes=await Promise.allSettled([submitResult(e,player,token,result(),1000000),submitResult(e,player,token,result(),1000000)]);
  assert.equal(outcomes.filter(r=>r.status==='fulfilled').length,1);
  assert.equal(e.sqlite.prepare('SELECT COUNT(*) AS n FROM submissions').get().n,1);
});
test('wrong player and impossible duration cannot submit',async()=>{
  const e=environment();const a=await register(e);const b=await register(e);
  const token=await runToken(e,a.player_id);
  await assert.rejects(submitResult(e,{id:b.player_id},token,result(),1000000));
  await assert.rejects(submitResult(e,{id:a.player_id},token,result({time_ms:1000}),1000000));
});
test('empty leaderboard honestly returns no scores, no user totals',async()=>{
  const e=environment();const p=await register(e);
  const r=await worker.fetch(request('/v1/leaderboard?mode=score_attack_120&ruleset='+RULESET+'&version='+VERSION,undefined,p.player_token,'GET'),e);
  const body=await r.json();assert.equal(r.status,200);
  assert.deepEqual(body.entries,[]);assert.deepEqual(body.ranks,{world:null,country:null,region:null});
  assert.equal('total_users' in body,false);
});
test('world country and region ranks are computed independently',async()=>{
  const e=environment();const profiles=[profile,{nickname:'OTHER',country:'JP',region:'TOKYO'},{nickname:'NODE',country:'US',region:'CA'}];
  const players=[];
  for(let i=0;i<3;i++) {
    const p=await register(e,profiles[i]);players.push(p);
    await submitResult(e,{id:p.player_id},await runToken(e,p.player_id),result({score:100+i*100}),1000000);
  }
  const r=await worker.fetch(request('/v1/leaderboard?mode=score_attack_120&ruleset='+RULESET+'&version='+VERSION,undefined,players[0].player_token,'GET'),e);
  const body=await r.json();assert.deepEqual(body.ranks,{world:3,country:2,region:1});
  assert.deepEqual(body.entries.map(r=>r.score),[300,200,100]);
  assert.equal('token_hash' in body.entries[0],false);
});
test('rate limits and missing infrastructure fail closed',async()=>{
  const e=environment();e.REGISTER_LIMITER.limit=async()=>({success:false});
  assert.equal((await worker.fetch(request('/v1/players',{profile,version:VERSION}),e)).status,429);
  assert.equal((await worker.fetch(request('/v1/players',{}),{})).status,503);
});
test('malformed JSON and private metadata are rejected',async()=>{
  const e=environment();
  assert.equal((await worker.fetch(request('/v1/players',{profile,version:VERSION,paths:['private']}),e)).status,400);
  const r=new Request('https://ranking.example.com/v1/players',{method:'POST',headers:{'Content-Type':'application/json'},body:'{'});
  assert.equal((await worker.fetch(r,e)).status,400);
  assert.equal((await worker.fetch(request('/v1/players',{profile,version:VERSION,padding:'x'.repeat(10000)}),e)).status,413);
});
test('database outage returns bounded error without SQL or traces',async()=>{
  const e=environment();e.DB.prepare=()=>{throw new Error('sensitive SQL');};
  const r=await worker.fetch(request('/v1/players',{profile,version:VERSION}),e);
  assert.equal(r.status,503);assert.doesNotMatch(await r.text(),/SQL|stack|sensitive/);
});

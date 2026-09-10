import {COUNTRIES} from './countries.mjs';
export const VERSION = '1.2.0';
export const RULESET = 'ruleset_1';
export const MODES = ['score_attack_120', 'sprint_40'];
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true });
const resultFields = ['mode','ruleset','version','score','time_ms','lines','pieces'];
const profileFields = ['nickname','country','region'];
const only = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every(k => keys.includes(k));
const hex = bytes => Array.from(bytes, b => b.toString(16).padStart(2,'0')).join('');
const randomToken = () => hex(crypto.getRandomValues(new Uint8Array(32)));
const response = (value, status=200) => Response.json(value, {status, headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
class ApiError extends Error { constructor(status, message) { super(message); this.status=status; } }
const check = (condition, status=400, message='Invalid request') => { if (!condition) throw new ApiError(status,message); };

export async function tokenHash(token) {
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(token))));
}

export function validProfile(p) {
  return only(p, profileFields) && typeof p.nickname === 'string' && /^[A-Za-z0-9_.-]{2,16}$/.test(p.nickname) && p.nickname.trim()===p.nickname
    && typeof p.country === 'string' && COUNTRIES.has(p.country)
    && typeof p.region === 'string' && /^[A-Z0-9 ._-]{1,32}$/.test(p.region) && p.region.trim()===p.region;
}

export function validResult(r) {
  if (!only(r,resultFields) || !MODES.includes(r.mode) || r.ruleset!==RULESET || r.version!==VERSION) return false;
  for (const [k,max] of [['score',100000000],['time_ms',86400000],['lines',10000],['pieces',25000]]) {
    if (!Number.isSafeInteger(r[k]) || r[k]<0 || r[k]>max) return false;
  }
  const level=1+Math.floor(r.lines/10);
  const bound=40*r.pieces+200*level*r.lines+25*level*r.lines*Math.max(0,r.lines-1);
  if (r.lines*10>r.pieces*4 || r.score>bound) return false;
  return r.mode==='score_attack_120'
    ? r.time_ms>0 && r.time_ms<=120000 && r.pieces<=2400
    : r.time_ms>=1000 && r.time_ms<=86400000 && r.lines>=40 && r.lines<=43 && r.pieces>=10;
}

async function key(secret) {
  check(typeof secret==='string' && secret.length>=32,503,'Ranking is not configured');
  return crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
}
const b64 = bytes => btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
function unb64(value) {
  check(typeof value==='string' && /^[A-Za-z0-9_-]+$/.test(value));
  return Uint8Array.from(atob(value.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));
}
export async function signRun(payload, secret) {
  const encoded=b64(encoder.encode(JSON.stringify(payload)));
  const signature=await crypto.subtle.sign('HMAC',await key(secret),encoder.encode(encoded));
  return encoded+'.'+b64(new Uint8Array(signature));
}
export async function verifyRun(token, secret, now=Date.now()) {
  check(typeof token==='string' && token.length<=2048,401,'Invalid run token');
  const [encoded,signature,extra]=token.split('.');
  check(encoded && signature && !extra,401,'Invalid run token');
  check(await crypto.subtle.verify('HMAC',await key(secret),unb64(signature),encoder.encode(encoded)),401,'Invalid run token');
  const value=JSON.parse(decoder.decode(unb64(encoded)));
  check(value.expires_ms>=now && value.issued_ms<=now,401,'Run token expired');
  return value;
}

async function readBody(request) {
  check((request.headers.get('Content-Type')||'').split(';')[0]==='application/json',415);
  check(Number(request.headers.get('Content-Length')||0)<=8192,413);
  const reader=request.body?.getReader();
  check(reader);
  const chunks=[];let length=0;
  for (;;) {
    const {value,done}=await reader.read(); if(done) break;
    length+=value.length;
    if(length>8192) { await reader.cancel(); throw new ApiError(413,'Request too large'); }
    chunks.push(value);
  }
  const bytes=new Uint8Array(length);let offset=0;
  for(const chunk of chunks) {bytes.set(chunk,offset);offset+=chunk.length;}
  try {return JSON.parse(decoder.decode(bytes));} catch {throw new ApiError(400,'Invalid JSON');}
}

async function authenticate(request, env) {
  const bearer=request.headers.get('Authorization')||'';
  check(/^Bearer [a-f0-9]{64}$/.test(bearer),401,'Invalid player token');
  const player=await env.DB.prepare('SELECT id,nickname,country,region FROM players WHERE token_hash=?').bind(await tokenHash(bearer.slice(7))).first();
  check(player,401,'Invalid player token');
  check((await env.REQUEST_LIMITER.limit({key:player.id})).success,429,'Please try again later');
  return player;
}

export async function submitResult(env, player, token, result, now=Date.now()) {
  check(validResult(result));
  const run=await verifyRun(token,env.RUN_SIGNING_KEY,now);
  check(run.player_id===player.id && run.mode===result.mode && run.ruleset===result.ruleset && run.version===result.version,401,'Run does not match result');
  const elapsed=now-run.issued_ms;
  check(result.time_ms<=elapsed+2000 && elapsed<=result.time_ms+15000,400,'Run duration does not match');
  // Deliberately generous sanity bounds, not proof of gameplay or anti-cheat.
  check(result.pieces<=Math.ceil(result.time_ms/50)+10,400,'Impossible piece count');
  const existing=await env.DB.prepare('SELECT id FROM runs WHERE id=? AND player_id=?').bind(run.id,player.id).first();
  check(existing,401,'Unknown run');
  const previous=await env.DB.prepare('SELECT run_id FROM submissions WHERE run_id=?').bind(run.id).first();
  check(!previous,409,'Result already submitted');
  const values=[player.id,result.mode,result.ruleset,result.score,result.time_ms,result.lines,result.pieces,result.version];
  try {
    await env.DB.batch([
      env.DB.prepare('INSERT INTO submissions(run_id,player_id,mode,ruleset,score,time_ms,lines,pieces,version) VALUES(?,?,?,?,?,?,?,?,?)').bind(run.id,...values),
      env.DB.prepare(`INSERT INTO personal_bests(player_id,mode,ruleset,score,time_ms,lines,pieces,version) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(player_id,mode,ruleset) DO UPDATE SET score=excluded.score,time_ms=excluded.time_ms,lines=excluded.lines,pieces=excluded.pieces,version=excluded.version
        WHERE (excluded.mode='score_attack_120' AND excluded.score>personal_bests.score)
           OR (excluded.mode='sprint_40' AND excluded.time_ms<personal_bests.time_ms)`).bind(...values)
    ]);
  } catch(error) {
    const duplicate=await env.DB.prepare('SELECT run_id FROM submissions WHERE run_id=?').bind(run.id).first();
    if(duplicate) throw new ApiError(409,'Result already submitted');
    throw error;
  }
  return {ok:true};
}

async function leaderboard(env, player, mode) {
  check(MODES.includes(mode));
  const metric=mode==='sprint_40'?'time_ms':'score';
  const order=mode==='sprint_40'?'ASC':'DESC';
  const rows=await env.DB.prepare(`SELECT p.nickname,p.country,p.region,b.mode,b.ruleset,b.version,b.score,b.time_ms,b.lines,b.pieces
    FROM personal_bests b JOIN players p ON p.id=b.player_id WHERE b.mode=? AND b.ruleset=? ORDER BY b.${metric} ${order},b.player_id LIMIT 100`).bind(mode,RULESET).all();
  const own=await env.DB.prepare('SELECT score,time_ms FROM personal_bests WHERE player_id=? AND mode=? AND ruleset=?').bind(player.id,mode,RULESET).first();
  const ranks={world:null,country:null,region:null};
  if(own) {
    for(const scope of ['world','country','region']) {
      const clauses=scope==='world'?'':(scope==='country'?' AND p.country=?':' AND p.country=? AND p.region=?');
      const binds=[mode,RULESET,own[metric]];
      if(scope!=='world') binds.push(player.country);
      if(scope==='region') binds.push(player.region);
      const r=await env.DB.prepare(`SELECT COUNT(*)+1 AS rank FROM personal_bests b JOIN players p ON p.id=b.player_id
        WHERE b.mode=? AND b.ruleset=? AND b.${metric}${order==='ASC'?'<':'>'}?${clauses}`).bind(...binds).first();
      ranks[scope]=r.rank;
    }
  }
  return {ok:true,entries:rows.results,ranks};
}

export default {
  async fetch(request,env) {
    try {
      check(env.DB && env.REQUEST_LIMITER && env.REGISTER_LIMITER,503,'Ranking is not configured');
      const url=new URL(request.url);
      check(url.protocol==='https:',400,'HTTPS required');
      if(request.method==='POST' && url.pathname==='/v1/players') {
        // No IP, geolocation, host metadata, analytics, or request logging.
        check((await env.REGISTER_LIMITER.limit({key:'registration'})).success,429,'Please try again later');
        const body=await readBody(request);
        check(only(body,['profile','version']) && body.version===VERSION && validProfile(body.profile));
        const id=crypto.randomUUID(),token=randomToken();
        await env.DB.prepare('INSERT INTO players(id,token_hash,nickname,country,region) VALUES(?,?,?,?,?)')
          .bind(id,await tokenHash(token),body.profile.nickname,body.profile.country,body.profile.region).run();
        return response({ok:true,player_id:id,player_token:token},201);
      }
      check((await env.REQUEST_LIMITER.limit({key:'public-requests'})).success,429,'Please try again later');
      const player=await authenticate(request,env);
      if(request.method==='POST' && url.pathname==='/v1/profile') {
        const body=await readBody(request);
        check(only(body,['profile','version']) && body.version===VERSION && validProfile(body.profile));
        await env.DB.prepare('UPDATE players SET nickname=?,country=?,region=? WHERE id=?')
          .bind(body.profile.nickname,body.profile.country,body.profile.region,player.id).run();
        return response({ok:true});
      }
      if(request.method==='GET' && url.pathname==='/v1/leaderboard') {
        check(url.searchParams.get('ruleset')===RULESET && url.searchParams.get('version')===VERSION);
        return response(await leaderboard(env,player,url.searchParams.get('mode')));
      }
      if(request.method==='POST' && url.pathname==='/v1/runs') {
        const body=await readBody(request);
        check(only(body,['mode','ruleset','version']) && MODES.includes(body.mode) && body.ruleset===RULESET && body.version===VERSION);
        const now=Date.now(),id=crypto.randomUUID();
        const payload={id,player_id:player.id,mode:body.mode,ruleset:RULESET,version:VERSION,seed:randomToken().slice(0,16),
                       issued_ms:now,expires_ms:now+(body.mode==='sprint_40'?86400000:120000)+15000};
        const token=await signRun(payload,env.RUN_SIGNING_KEY);
        await env.DB.prepare('INSERT INTO runs(id,player_id,mode,ruleset,issued_ms,expires_ms) VALUES(?,?,?,?,?,?)')
          .bind(id,player.id,body.mode,RULESET,now,payload.expires_ms).run();
        return response({ok:true,run_token:token,seed:payload.seed});
      }
      if(request.method==='POST' && url.pathname==='/v1/results') {
        const body=await readBody(request);
        check(only(body,['run_token','result']));
        return response(await submitResult(env,player,body.run_token,body.result));
      }
      throw new ApiError(404,'Not found');
    } catch(error) {
      return response({ok:false,error:error instanceof ApiError?error.message:'Ranking is temporarily unavailable'},error instanceof ApiError?error.status:503);
    }
  }
};

"""Real Qt UI regression checks and deterministic offscreen review artifacts."""
import os


def run(n, app, folder, output=None):
    C, G, W = n.QtCore,n.QtGui,n.QtWidgets
    original_path = n.user_settings_path
    original_probe = n.studio_folder_status
    panels = []

    def panel(name):
        n.user_settings_path=lambda:os.path.join(folder,name+'.json')
        widget=n.NukerisPanel()
        widget.resize(800,800)
        panels.append(widget)
        return widget

    def save_image(widget,name):
        if output:
            assert widget.grab().save(os.path.join(output,'polish_'+name+'.png'))

    class Recorder(object):
        def __init__(self,painter):
            self.painter=painter
            self.text=[]
            self.lines=[]
        def __getattr__(self,name):return getattr(self.painter,name)
        def drawText(self,*args):
            self.text.append(args[-1])
            return self.painter.drawText(*args)
        def drawLine(self,*args):
            self.lines.append(args)
            return self.painter.drawLine(*args)

    try:
        fresh=panel('fresh-polish')
        fresh.show();app.processEvents()
        assert fresh.network.transport.manager is None
        settings=n.SettingsDialog(fresh)
        assert not settings.online.isChecked() and not settings.studio.isChecked()
        assert not settings.test.isEnabled() and not settings.folder.isEnabled()
        def unexpected(*args):raise AssertionError('Studio I/O while off')
        n.studio_folder_status=unexpected
        settings.test_folder()
        fresh.network.endpoint='https://ranking.example.com'
        replies=[]
        fresh.network.leaderboard(n.SCORE_ATTACK,replies.append)
        assert len(replies)==1 and not replies[0]['ok']
        assert fresh.network.transport.manager is None
        settings.save()
        assert fresh.settings.read()['profile']=={}
        assert not fresh.settings.read()['studio_enabled']
        assert not fresh.settings.read()['global_enabled']
        n.studio_folder_status=original_probe

        existing=panel('existing-polish')
        existing.settings.save_preferences(dict(global_enabled=True,studio_enabled=True,
            studio_folder=folder,studio_player_id='a'*32,player_id='b'*36,player_token='c'*64,
            profile=dict(nickname='MORI',country='JP',region='TOKYO')))
        existing.settings.save_best(26605)
        from test_settings import result
        existing.settings.record(result())
        existing.settings.record(result(n.SPRINT,time_ms=37281))
        existing.preferences=existing.settings.read()
        original=existing.settings.read()
        settings=n.SettingsDialog(existing)
        settings.show();app.processEvents()
        assert settings.country.currentText()=='Japan'
        assert settings.country.currentData()=='JP'
        assert settings.region.count()==48
        assert settings.region.currentText()=='Tokyo'
        assert settings.region.currentData()=='TOKYO'
        assert settings.online.isChecked() and settings.studio.isChecked()
        settings.folder.setText('//studio/tools/nukeris-ranking')
        save_image(settings,'settings_japan')
        settings.folder.setText(folder)
        settings.save()
        assert existing.settings.read()==original
        assert existing.network.transport.manager is None
        # Opening a new pane with persisted opt-ins must still send no request.
        reopened=n.NukerisPanel()
        panels.append(reopened)
        assert reopened.preferences['global_enabled'] and reopened.preferences['studio_enabled']
        assert reopened.network.transport.manager is None

        settings=n.SettingsDialog(existing)
        settings.country.setCurrentIndex(settings.country.findData('US'))
        assert settings.region.isEditable() and settings.region.currentText()==''
        settings.region.setEditText('New York')
        settings.country.setCurrentIndex(settings.country.findData('JP'))
        assert settings.region.currentText()=='Tokyo'
        settings.region.setCurrentIndex(settings.region.findData('JP-11'))
        settings.save()
        assert existing.settings.read()['profile']['region']=='JP-11'
        for key in ('pbs','ranked_pbs','player_id','player_token','studio_player_id','studio_folder'):
            assert existing.settings.read()[key]==original[key],key
        settings=n.SettingsDialog(existing)
        settings.country.setCurrentIndex(settings.country.findData('US'))
        settings.region.setEditText('invalid!')
        before=existing.settings.read()
        settings.save()
        assert existing.settings.read()==before
        settings.region.setEditText('')
        settings.save()
        assert existing.settings.read()['profile']['region']=='-'
        assert n.validate_profile(existing.settings.read()['profile'])

        # Failed persistence leaves the complete previous settings file intact.
        settings=n.SettingsDialog(existing)
        settings.grid.setChecked(not settings.grid.isChecked())
        previous=existing.settings.read()
        save_preferences=existing.settings.save_preferences
        existing.settings.save_preferences=lambda values:False
        settings.save()
        assert existing.settings.read()==previous
        existing.settings.save_preferences=save_preferences
        settings.close()

        settings=n.SettingsDialog(fresh)
        settings.folder.setText(folder)
        settings.studio.setChecked(True)
        settings.test_folder()
        loop=C.QEventLoop()
        C.QTimer.singleShot(100,loop.quit)
        (getattr(loop,'exec',None) or loop.exec_)()
        assert settings.studio_status.text()=='Available',settings.studio_status.text()
        settings.studio.setChecked(False)
        assert settings.studio_status.text()=='Offline'
        settings.close()
        privacy=n.PrivacyDialog(fresh)
        privacy.show();app.processEvents()
        save_image(privacy,'privacy')
        privacy.close()

        # Test timer hierarchy and actual painted texts, not only helper return values.
        fresh.engine.score=156
        fresh.engine.best_score=26605
        fresh._active_seconds=14
        for mode,elapsed,expected in ((n.NORMAL,14000,''),(n.SCORE_ATTACK,17700,'01:42.3'),(n.SPRINT,37281,'00:37.281')):
            fresh.session=n.GameSession(mode,seed=11)
            fresh.session.elapsed_ms=elapsed
            image=G.QImage(800,800,n._enum_value(G.QImage,'Format','Format_ARGB32'))
            painter=G.QPainter(image)
            recorder=Recorder(painter)
            fresh._draw_header(recorder,12,800,fresh._theme())
            assert expected in recorder.text
            if mode==n.NORMAL:
                assert '00:14' not in recorder.text
            rows=dict((key,value) for key,value,_ in fresh._stats_rows())
            assert rows['level']=='1' and rows['lines']=='0'
            assert ('time' in rows)==(mode==n.NORMAL)
            if mode==n.NORMAL:assert rows['time']=='00:14'
            recorder.text=[]
            board=C.QRectF(*n.panel_layout(800,800)['board'])
            fresh._draw_board(recorder,board,n.panel_layout(800,800)['cell'],fresh._theme())
            assert n.PANEL_TITLE not in recorder.text
            painter.end()

        # Four cardinal wires meet the renderer's exact node edges after height changes.
        image=G.QImage(200,200,n._enum_value(G.QImage,'Format','Format_ARGB32'))
        painter=G.QPainter(image);recorder=Recorder(painter)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            src,dst=(2,2),(2+dx,2+dy)
            fresh._draw_nuke_wire(recorder,C.QRectF(0,0,200,200),30,src,dst,fresh._theme())
            a,b=recorder.lines[-1]
            r=fresh._node_rect(C.QRectF(0,0,200,200),30,*src)
            assert abs(a.x()-(r.center().x()+dx*r.width()/2))<.001
            assert abs(a.y()-(r.center().y()+dy*r.height()/2))<.001
            assert a.x()==b.x() or a.y()==b.y()
        painter.end()

        # Deterministic game-state fixture for visual review; no online records.
        fresh.session=n.GameSession(n.NORMAL,seed=7)
        fresh.engine=fresh.session.engine
        fresh.started=True;fresh.paused=True
        fresh._active_seconds=14
        fresh.engine.score=156;fresh.engine.best_score=26605
        for group,(kind,ox,oy) in enumerate((('J',0,17),('T',4,17),('Z',7,17),('I',0,18))):
            for x,y in n.PIECE_CELLS[kind][0]:
                if 0<=x+ox<10 and 0<=y+oy<20:
                    fresh.engine.board[y+oy][x+ox]=n.PlacedCell(kind,group+1)
        fresh.engine.active=n.Tetromino('T')
        fresh.engine.active.x,fresh.engine.active.y=3,7
        fresh.engine.hold_kind='J'
        fresh._grid_checkbox.setChecked(True)
        for width,height,name in ((800,800,'standard'),(360,600,'compact'),(500,1000,'tall')):
            fresh.resize(width,height);fresh.show();app.processEvents()
            assert not fresh.error_text,fresh.error_text
            for button in (fresh._ranking_button,fresh._settings_button,fresh._new_game_button):
                assert button.isVisible() and fresh.rect().contains(button.geometry())
            assert not fresh._mode_combo.geometry().intersects(fresh._settings_button.geometry())
            save_image(fresh,name+'_paused')
            fresh.paused=False;fresh.update();app.processEvents()
            save_image(fresh,name+'_playing')
            fresh.paused=True
        fresh.resize(800,800);app.processEvents()
        board=C.QRectF(*n.panel_layout(800,800)['board'])
        image=G.QImage(800,800,n._enum_value(G.QImage,'Format','Format_ARGB32'))
        image.fill(G.QColor('#9B6B99'))
        painter=G.QPainter(image)
        fresh._draw_overlay(painter,board,fresh._theme())
        painter.end()
        sample=G.QColor(image.pixel(int(board.left()+8),int(board.bottom()-40)))
        assert max(abs(a-b) for a,b in zip(sample.getRgb()[:3],(155,107,153)))<25
        for mode,name in ((n.SCORE_ATTACK,'score_attack'),(n.SPRINT,'sprint')):
            fresh.session=n.GameSession(mode,seed=1)
            fresh.session.elapsed_ms=17700 if mode==n.SCORE_ATTACK else 37281
            fresh._mode_combo.setCurrentIndex(n.MODES.index(mode))
            fresh.paused=False;fresh.update();app.processEvents()
            save_image(fresh,name)
        assert fresh.network.transport.manager is None
        print('UI polish checks passed: timers, stats, opt-ins, profile round-trip, save failure, Studio TEST, geometry, pause, layouts and badge absence.')
    finally:
        for widget in panels:widget.close()
        app.processEvents()
        n.user_settings_path=original_path
        n.studio_folder_status=original_probe

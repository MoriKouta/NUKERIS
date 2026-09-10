import threading
_RANKING_WORKERS = set()

class RankingIO(QtCore.QObject):
    delivered = QtCore.Signal(object)
    finished = QtCore.Signal()
    def __init__(self, operation):
        QtCore.QObject.__init__(self)
        self.operation = operation
    def start(self):
        thread = threading.Thread(target=self.run, name='NUKERIS Studio request')
        thread.daemon = True
        thread.start()
    def run(self):
        try:
            try:
                value = self.operation()
            except Exception:
                value = dict(ok=False, entries=[], message='Ranking is unavailable. Personal records are safe.')
            try:
                self.delivered.emit(value)
                self.finished.emit()
            except RuntimeError:
                pass  # The host may have closed while the filesystem was unavailable.
        finally:
            _RANKING_WORKERS.discard(self)


def run_ranking_io(operation, receiver=None):
    if len(_RANKING_WORKERS) >= 2:
        if receiver:
            receiver(dict(ok=False, entries=[], message='A Studio operation is still pending. Personal records are safe.'))
        return None
    worker = RankingIO(operation)
    _RANKING_WORKERS.add(worker)
    if receiver is not None:
        worker.delivered.connect(receiver)
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, panel):
        QtWidgets.QDialog.__init__(self, panel)
        self.panel = panel
        self.setWindowTitle('NUKERIS SETTINGS')
        form = QtWidgets.QFormLayout(self)
        self.grid = QtWidgets.QCheckBox('Node Graph grid')
        self.grid.setChecked(panel.preferences['grid'])
        self.studio = QtWidgets.QCheckBox('Enable Studio shared-folder ranking')
        self.studio.setChecked(panel.preferences['studio_enabled'])
        self.folder = QtWidgets.QLineEdit(panel.preferences['studio_folder'])
        self.online = QtWidgets.QCheckBox('Enable Global online ranking (HTTPS)')
        self.online.setChecked(panel.preferences['global_enabled'])
        profile = panel.preferences['profile']
        self.nickname = QtWidgets.QLineEdit(profile.get('nickname',''))
        self.nickname.setMaxLength(16)
        self.country = QtWidgets.QComboBox()
        self.country.addItems([''] + COUNTRY_CODES)
        self.country.setCurrentIndex(max(0,self.country.findText(profile.get('country',''))))
        self.region = QtWidgets.QLineEdit(profile.get('region',''))
        self.region.setMaxLength(32)
        note = QtWidgets.QLabel('Ranking shares your nickname, manually selected area and result.\n'
                                'No email, account, location lookup or Nuke project data.\n'
                                'Studio uses only the folder you enter and existing OS permissions.\n'
                                'Turning Global on alone sends no request. Use ranking actions to connect.')
        note.setWordWrap(True)
        form.addRow(note)
        form.addRow(self.grid)
        form.addRow(self.studio)
        form.addRow('Studio folder',self.folder)
        form.addRow(self.online)
        form.addRow('Public nickname',self.nickname)
        form.addRow('Country (manual)',self.country)
        form.addRow('Region / Prefecture (manual)',self.region)
        self.message = QtWidgets.QLabel('Nickname: 2-16 letters, numbers, _, - or .')
        self.message.setWordWrap(True)
        form.addRow(self.message)
        save = QtWidgets.QPushButton('SAVE')
        save.clicked.connect(self.save)
        form.addRow(save)

    def save(self):
        profile = dict(nickname=self.nickname.text().strip(),country=self.country.currentText(),
                       region=self.region.text().strip().upper())
        if (self.studio.isChecked() or self.online.isChecked()) and not validate_profile(profile):
            self.message.setText('Enter a valid nickname, country and region (A-Z, 0-9, space, _, - or .).')
            return
        folder = self.folder.text().strip()
        if self.studio.isChecked() and not os.path.isabs(folder):
            self.message.setText('Enter the absolute Studio folder path.')
            return
        values = dict(grid=self.grid.isChecked(), studio_enabled=self.studio.isChecked(),
                      global_enabled=self.online.isChecked(), studio_folder=folder, profile=profile)
        if self.studio.isChecked() and not self.panel.preferences['studio_player_id']:
            values['studio_player_id'] = uuid.uuid4().hex
        if not self.panel.settings.save_preferences(values):
            self.message.setText(self.panel.settings.last_error)
            return
        self.panel.preferences = self.panel.settings.read()
        self.panel._grid_checkbox.setChecked(values['grid'])
        if hasattr(self.panel, 'network'):
            self.panel.network.configure(values['global_enabled'])
        self.accept()


class RankingDialog(QtWidgets.QDialog):
    def __init__(self, panel):
        QtWidgets.QDialog.__init__(self, panel)
        self.panel = panel
        self.setWindowTitle('NUKERIS RANKING')
        self.resize(620,480)
        layout = QtWidgets.QVBoxLayout(self)
        self.scope = QtWidgets.QComboBox()
        self.scope.addItems(['PERSONAL','STUDIO','GLOBAL'])
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(MODE_LABELS[1:])
        self.refresh = QtWidgets.QPushButton('REFRESH')
        self.refresh.clicked.connect(self.load)
        layout.addWidget(self.scope)
        layout.addWidget(self.mode)
        layout.addWidget(self.refresh)
        self.table = QtWidgets.QTableWidget(0,4)
        self.table.setHorizontalHeaderLabels(['#','PLAYER','AREA','RESULT'])
        self.table.setEditTriggers(_enum_value(QtWidgets.QAbstractItemView,'EditTrigger','NoEditTriggers'))
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.ranks = QtWidgets.QLabel()
        layout.addWidget(self.ranks)
        self.load()

    def load(self):
        mode = MODES[self.mode.currentIndex()+1]
        scope = self.scope.currentIndex()
        self.table.setRowCount(0)
        self.ranks.setText('')
        if scope == 0:
            r = self.panel.settings.personal().get(mode+'/'+RULESET)
            self.display(dict(ok=True,entries=[dict(r,nickname='YOU',country='',region='')] if r else []))
            self.status.setText('NORMAL BEST  {0:,} | Personal records are fully offline.'.format(self.panel.settings.best()))
        elif scope == 1:
            self.refresh.setEnabled(False)
            self.status.setText('Reading the configured Studio folder...')
            store = self.panel._studio_store()
            run_ranking_io(lambda: store.read(mode), self.display)
        else:
            self.status.setText('Global ranking is not configured yet. Personal records are safe.')

    def display(self, response):
        self.refresh.setEnabled(True)
        entries = response.get('entries', [])
        self.table.setRowCount(len(entries))
        for i, row in enumerate(entries):
            value = format_milliseconds(row['time_ms']) if row['mode']==SPRINT else '{0:,}'.format(row['score'])
            for j, text in enumerate((str(i+1), row.get('nickname',''),
                                      row.get('country','')+' / '+row.get('region',''), value)):
                self.table.setItem(i,j,QtWidgets.QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        self.status.setText(response.get('message') or ('' if entries else 'NO SCORES YET\nSet the first record.'))

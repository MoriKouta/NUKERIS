class PrivacyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self,parent)
        self.setWindowTitle('PRIVACY & NETWORK INFO')
        self.resize(520,390)
        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QTextBrowser()
        info.setOpenExternalLinks(False)
        info.setPlainText(
            'OFFLINE BY DEFAULT\n'
            'Installing, importing or opening NUKERIS starts no network request. '
            'Studio and Global are off in fresh settings.\n\n'
            'No telemetry, analytics, LAN discovery, listening ports, background '
            'services, automatic updates or automatic geolocation.\n\n'
            'NUKE ISOLATION\n'
            'NUKERIS does not inspect or send Nuke scripts, nodes, knobs, paths, '
            'project data, frames, Viewer, account or license information. '
            'It does not change your comp or Undo stack.\n\n'
            'STUDIO\n'
            'Only your explicitly selected shared folder is accessed after opt-in. '
            'Existing OS permissions are used; no NAS password is stored. '
            'TEST checks reported permissions without writing a score. '
            'An OS file operation already in progress may finish after disabling.\n\n'
            'GLOBAL\n'
            'After opt-in, explicit ranking actions and enabled challenge runs use '
            'asynchronous HTTPS. Enabling Global alone sends no request. '
            'Only the public profile, player/run credentials and required ranking '
            'results, mode, ruleset and NUKERIS version are sent. '
            'Country and region are chosen manually.\n\n'
            'Your player token is private and stored in local settings. Do not share '
            'that file. Personal results remain independent of external failures.')
        layout.addWidget(info)
        close = QtWidgets.QPushButton('CLOSE')
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, panel):
        QtWidgets.QDialog.__init__(self,panel)
        self.panel = panel
        self.setWindowTitle('NUKERIS SETTINGS')
        self.resize(490,560)
        self._test_cancel = threading.Event()
        self._test_serial = 0
        self._testing = False
        self._profile = dict(panel.preferences['profile'])
        self._country_code = self._profile.get('country','')
        self._regions = {self._country_code:self._profile.get('region','')}
        layout = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_enum_value(QtWidgets.QFrame,'Shape','NoFrame'))
        content = QtWidgets.QWidget()
        sections = QtWidgets.QVBoxLayout(content)
        sections.setContentsMargins(0,0,4,0)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        def section(title):
            group = QtWidgets.QGroupBox(title)
            form = QtWidgets.QFormLayout(group)
            form.setFieldGrowthPolicy(_enum_value(QtWidgets.QFormLayout,'FieldGrowthPolicy','AllNonFixedFieldsGrow'))
            sections.addWidget(group)
            return form

        display = section('DISPLAY')
        self.grid = QtWidgets.QCheckBox('Node Graph grid')
        self.grid.setChecked(panel.preferences['grid'])
        display.addRow(self.grid)

        studio = section('STUDIO RANKING')
        self.studio = QtWidgets.QCheckBox('Enable Studio Ranking')
        self.studio.setChecked(panel.preferences['studio_enabled'])
        self.folder = QtWidgets.QLineEdit(panel.preferences['studio_folder'])
        self.folder.setPlaceholderText('Absolute shared folder path')
        self.test = QtWidgets.QPushButton('TEST')
        self.test.setMaximumWidth(66)
        self.test.setToolTip('Check availability and reported read/write permissions. No score or test file is written.')
        self.studio_status = QtWidgets.QLabel('Not tested' if self.studio.isChecked() else 'Offline')
        test_row = QtWidgets.QHBoxLayout()
        test_row.addWidget(self.test)
        test_row.addWidget(self.studio_status,1)
        studio.addRow(self.studio)
        studio.addRow('Shared folder',self.folder)
        studio.addRow(test_row)

        global_form = section('GLOBAL RANKING')
        self.online = QtWidgets.QCheckBox('Enable Global Ranking')
        self.online.setChecked(panel.preferences['global_enabled'])
        self.nickname = QtWidgets.QLineEdit(self._profile.get('nickname',''))
        self.nickname.setMaxLength(16)
        self.nickname.setToolTip('2-16 letters, numbers, underscore, hyphen or dot.')
        self.country = QtWidgets.QComboBox()
        self.country.addItem('Choose country','')
        for code in sorted(COUNTRY_CODES,key=lambda c:country_label(c)):
            self.country.addItem(country_label(code),code)
        self.country.setCurrentIndex(max(0,self.country.findData(self._country_code)))
        self.region = QtWidgets.QComboBox()
        self.region.setInsertPolicy(_enum_value(QtWidgets.QComboBox,'InsertPolicy','NoInsert'))
        self.region_hint = QtWidgets.QLabel()
        self.region_hint.setWordWrap(True)
        self._populate_regions()
        global_form.addRow(self.online)
        shared_profile = QtWidgets.QLabel('Public profile used by Studio and Global.')
        global_form.addRow(shared_profile)
        global_form.addRow('Nickname',self.nickname)
        global_form.addRow('Country',self.country)
        global_form.addRow('Region / Prefecture',self.region)
        global_form.addRow(self.region_hint)

        network = section('NETWORK')
        self.network_status = QtWidgets.QLabel()
        self.network_status.setWordWrap(True)
        network.addRow(self.network_status)
        sections.addStretch(1)
        self.message = QtWidgets.QLabel('Changes apply on SAVE. TEST uses the selected Studio folder only.')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        buttons = QtWidgets.QHBoxLayout()
        self.privacy_button = QtWidgets.QPushButton('PRIVACY & NETWORK INFO')
        self.privacy_button.setFlat(True)
        self.privacy_button.clicked.connect(self.show_privacy)
        buttons.addWidget(self.privacy_button)
        buttons.addStretch(1)
        cancel = QtWidgets.QPushButton('CANCEL')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.save_button = QtWidgets.QPushButton('SAVE')
        self.save_button.clicked.connect(self.save)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.test.clicked.connect(self.test_folder)
        self.studio.toggled.connect(self._studio_changed)
        self.online.toggled.connect(self._sync_enabled)
        self.folder.textChanged.connect(self._studio_changed)
        self.country.currentIndexChanged.connect(self._country_changed)
        self.finished.connect(self._cancel_test)
        self._sync_enabled()

    def _region_code(self):
        if self.region.isEditable():
            text = self.region.currentText().strip()
            stored = self._regions.get(self._country_code,'')
            if text == region_label(self._country_code,stored):
                return stored or '-'
            return text.upper() or '-'
        return self.region.currentData() or ''

    def _populate_regions(self):
        country = self._country_code
        stored = self._regions.get(country,'')
        self.region.clear()
        choices = REGION_CHOICES.get(country)
        self.region.setEditable(not bool(choices))
        if choices:
            self.region.addItem('Choose prefecture','')
            canonical = canonical_region(country,stored)
            selected = 0
            for code,label in choices:
                self.region.addItem(label,stored if code == canonical and stored else code)
                if code == canonical:
                    selected = self.region.count()-1
            if stored and not selected:
                self.region.addItem(region_label(country,stored) or 'Saved region',stored)
                selected = self.region.count()-1
            self.region.setCurrentIndex(selected)
            self.region_hint.setText('Choose a prefecture. Your saved value is kept until you change it.')
        else:
            self.region.lineEdit().setMaxLength(32)
            self.region.lineEdit().setPlaceholderText('Optional region name')
            self.region.setEditText(region_label(country,stored))
            self.region_hint.setText('Optional region name; no bundled list for this country.' if country else 'Choose a country to see available regions.')
            self.region.setToolTip('Optional name: letters, numbers, spaces, _, - or .')

    def _country_changed(self, _index):
        self._regions[self._country_code] = self._region_code()
        self._country_code = self.country.currentData() or ''
        self._populate_regions()

    def _sync_enabled(self, *_args):
        studio, online = self.studio.isChecked(), self.online.isChecked()
        self.folder.setEnabled(studio)
        self.test.setEnabled(studio and not self._testing and bool(self.folder.text().strip()))
        for field in (self.nickname,self.country,self.region):
            field.setEnabled(studio or online)
        if studio and online:
            text = 'Studio shared-folder ranking and Global ranking via HTTPS are enabled.'
        elif studio:
            text = 'Studio shared-folder ranking enabled.\nGlobal network access is disabled.'
        elif online:
            text = 'Global ranking enabled via HTTPS.\nStudio shared-folder access is disabled.'
        else:
            text = 'Offline\nNo network connections or shared-folder access while both rankings are disabled.'
        self.network_status.setText(text)

    def _cancel_test(self, *_args):
        self._test_cancel.set()
        self._test_serial += 1

    def _studio_changed(self, *_args):
        self._cancel_test()
        self._testing = False
        self.studio_status.setText('Not tested' if self.studio.isChecked() else 'Offline')
        self._sync_enabled()

    def test_folder(self):
        if not self.studio.isChecked() or self._testing:
            return
        folder = self.folder.text().strip()
        if not os.path.isabs(folder):
            self.studio_status.setText('Error: absolute path required')
            return
        self._cancel_test()
        self._test_cancel = threading.Event()
        cancel = self._test_cancel
        serial = self._test_serial
        self._testing = True
        self.studio_status.setText('Checking...')
        self._sync_enabled()
        def operation():
            return dict(serial=serial, result=studio_folder_status(True,folder,cancel.is_set))
        run_ranking_io(operation,self._test_finished)

    @QtCore.Slot(object)
    def _test_finished(self, response):
        if response.get('serial',self._test_serial) != self._test_serial:
            return
        self._testing = False
        self.studio_status.setText(response.get('result',{}).get('status','Error: another Studio operation is pending'))
        self._sync_enabled()

    def show_privacy(self):
        dialog = PrivacyDialog(self)
        (getattr(dialog,'exec',None) or dialog.exec_)()

    def save(self):
        profile = dict(self._profile)
        nickname = self.nickname.text().strip()
        country = self.country.currentData() or ''
        region = self._region_code()
        if nickname or country or self._profile:
            profile.update(nickname=nickname,country=country,region=region)
        if (self.studio.isChecked() or self.online.isChecked() or profile) and not validate_profile(profile):
            self.message.setText('Choose a country, a valid nickname and a prefecture (Japan). Region text must use A-Z, 0-9, space, _, - or .')
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
        self.panel._studio_cancel.set()
        self.panel._studio_cancel = threading.Event()
        self.panel._grid_checkbox.setChecked(values['grid'])
        self.panel.network.configure(values['global_enabled'])
        self.accept()

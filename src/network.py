class QtNetworkTransport(QtCore.QObject):
    """Lazy asynchronous HTTP, bounded responses, hard timeout, no redirects."""
    def __init__(self, parent=None):
        QtCore.QObject.__init__(self,parent)
        self.manager = None
        self.pending = set()
        self.timeout_ms = 10000

    def cancel(self):
        for reply in list(self.pending):
            reply.abort()

    def request(self, method, url, body, token, callback):
        if len(self.pending)>=2:
            callback(dict(ok=False))
            return
        if self.manager is None:
            self.manager = QtNetwork.QNetworkAccessManager(self)
            self.manager.setProxy(QtNetwork.QNetworkProxy(_enum_value(QtNetwork.QNetworkProxy,'ProxyType','NoProxy')))
        request = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(b'User-Agent',('NUKERIS/'+__version__).encode('ascii'))
        request.setRawHeader(b'Accept',b'application/json')
        for attr in ('CookieLoadControlAttribute','CookieSaveControlAttribute','AuthenticationReuseAttribute'):
            request.setAttribute(_enum_value(QtNetwork.QNetworkRequest,'Attribute',attr),
                                 _enum_value(QtNetwork.QNetworkRequest,'LoadControl','Manual'))
        request.setAttribute(_enum_value(QtNetwork.QNetworkRequest,'Attribute','RedirectPolicyAttribute'),
                             _enum_value(QtNetwork.QNetworkRequest,'RedirectPolicy','ManualRedirectPolicy'))
        if token:
            request.setRawHeader(b'Authorization',('Bearer '+token).encode('ascii'))
        if method == 'GET':
            reply = self.manager.get(request)
        else:
            request.setRawHeader(b'Content-Type',b'application/json')
            reply = self.manager.post(request,QtCore.QByteArray(json.dumps(body,allow_nan=False).encode('utf-8')))
        self.pending.add(reply)
        reply.setReadBufferSize(16384)
        data = [bytearray()]
        timer = QtCore.QTimer(reply)
        timer.setSingleShot(True)
        timer.timeout.connect(reply.abort)
        timer.start(self.timeout_ms)
        def read():
            data[0].extend(bytes(reply.readAll()))
            if len(data[0])>131072:
                reply.abort()
        def finish():
            timer.stop()
            read()
            self.pending.discard(reply)
            value = dict(ok=False)
            try:
                status = reply.attribute(_enum_value(QtNetwork.QNetworkRequest,'Attribute','HttpStatusCodeAttribute'))
                no_error = _enum_value(QtNetwork.QNetworkReply,'NetworkError','NoError')
                if reply.error()==no_error and status is not None and 200<=int(status)<300 and len(data[0])<=131072:
                    value = json.loads(bytes(data[0]).decode('utf-8'))
            except (ValueError,TypeError,UnicodeError):
                pass
            reply.deleteLater()
            try:
                callback(value)
            except RuntimeError:
                pass  # A UI receiver may have closed during the request.
        reply.readyRead.connect(read)
        reply.finished.connect(finish)
        reply.sslErrors.connect(lambda _errors: reply.abort())

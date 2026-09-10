"""Exercise the real Qt transport with in-memory QNetworkReply objects."""
def run(nukeris, app):
    C, N = nukeris.QtCore, nukeris.QtNetwork
    attr = lambda name: nukeris._enum_value(N.QNetworkRequest,'Attribute',name)
    enum = lambda name: nukeris._enum_value(N.QNetworkReply,'NetworkError',name)

    class Reply(N.QNetworkReply):
        def __init__(self, payload, status=200, pending=False):
            N.QNetworkReply.__init__(self)
            self.payload=payload
            self.setAttribute(attr('HttpStatusCodeAttribute'),status)
            self.open(nukeris._enum_value(C.QIODevice,'OpenModeFlag','ReadOnly'))
            if not pending:
                C.QTimer.singleShot(0,self.deliver)
        def isSequential(self):return True
        def bytesAvailable(self):return len(self.payload)+N.QNetworkReply.bytesAvailable(self)
        def readData(self,size):
            data,self.payload=self.payload[:size],self.payload[size:]
            return data
        def deliver(self):
            self.readyRead.emit()
            if not self.isFinished():
                self.setFinished(True)
                self.finished.emit()
        def abort(self):
            if not self.isFinished():
                self.setError(enum('OperationCanceledError'),'test cancellation')
                self.setFinished(True)
                self.finished.emit()

    class Manager(object):
        def __init__(self,payload,status=200,pending=False):
            self.payload,self.status,self.pending=payload,status,pending
            self.requests=[]
        def get(self,request):
            self.requests.append(request)
            return Reply(self.payload,self.status,self.pending)
        def post(self,request,body):return self.get(request)

    for payload,status,pending,expected in [(b'{"ok":true}',200,False,True),
            (b'{',200,False,False),(b'{"ok":true}',302,False,False),
            (b'x'*140000,200,False,False),(b'',200,True,False)]:
        transport=nukeris.QtNetworkTransport()
        transport.timeout_ms=5
        manager=Manager(payload,status,pending)
        transport.manager=manager
        responses=[]
        transport.request('GET','https://ranking.example.com/v1/test',None,'a'*64,responses.append)
        loop=C.QEventLoop()
        C.QTimer.singleShot(30,loop.quit)
        (getattr(loop,'exec',None) or loop.exec_)()
        assert len(responses)==1,responses
        assert (responses[0].get('ok') is True)==expected,responses
        assert not transport.pending
        request=manager.requests[0]
        try:
            authorization=request.rawHeader(b'Authorization')
        except TypeError:
            # Newer Qt bindings expose the getter using a string view.
            authorization=request.rawHeader('Authorization')
        assert bytes(authorization)==b'Bearer '+b'a'*64
    print('Qt transport checks passed: success, malformed JSON, redirect, oversized response, timeout.')

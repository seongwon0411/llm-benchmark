import pytest
from api_client import ApiClient

def test_success_cached():
    calls=[]
    def tr(k): calls.append(k); return 200, {'v':1}
    c=ApiClient(tr)
    assert c.get('a') == {'v':1}
    assert c.get('a') == {'v':1}
    assert len(calls)==1

def test_500_retried_then_success():
    seq=[(500,None),(503,None),(200,'ok')]
    def tr(k): return seq.pop(0)
    c=ApiClient(tr,max_retries=2)
    assert c.get('x')=='ok'

def test_429_retried():
    seq=[(429,None),(200,'ok')]
    def tr(k): return seq.pop(0)
    c=ApiClient(tr,max_retries=2)
    assert c.get('x')=='ok'

def test_404_not_retried():
    calls=[]
    def tr(k): calls.append(k); return 404,None
    c=ApiClient(tr,max_retries=3)
    with pytest.raises(RuntimeError): c.get('x')
    assert len(calls)==1

def test_failure_not_cached():
    state={'n':0}
    def tr(k):
        state['n']+=1
        return (503,None) if state['n']<=2 else (200,'recovered')
    c=ApiClient(tr,max_retries=1)
    with pytest.raises(RuntimeError): c.get('x')
    assert c.get('x')=='recovered'

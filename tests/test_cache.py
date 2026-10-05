from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
import httpx
from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.circuit import Parameter
from qiskit.primitives import StatevectorSampler, BitArray, DataBin, SamplerPubResult, PrimitiveResult
from openshots.cache import SamplerCache,CachedResult,CachedJob,_joint_counts

class V2Sampler:
    backend=SimpleNamespace(name='device',simulator=False)
    def __init__(self):
        self.calls=[]
    def run(self, pubs, *, shots=None):
        self.calls.append((pubs,shots))
        return StatevectorSampler(seed=123).run(pubs,shots=shots)

def client(hits):
    c=Mock()
    c.sample_cache.side_effect=hits
    return c

def hit(counts):
    return {'hit':True,'counts':counts,'collection_ids':['old-run'], 'shots':sum(counts.values())}

def circuit():
    q=QuantumRegister(2,'q');a=ClassicalRegister(1,'alpha');b=ClassicalRegister(1,'beta')
    qc=QuantumCircuit(q,a,b);qc.h(0);qc.cx(0,1);qc.measure(0,a);qc.measure(1,b)
    return qc

def test_normalization_rejects_wrong_shot_total():
    assert CachedResult.from_counts({'00':5,'11':5}).quasi_dists==[{0:0.5,3:0.5}]
    with pytest.raises(ValueError): CachedResult.from_counts({'00':5,'11':5},20)

def test_v2_batch_and_joint_registers():
    sampler=V2Sampler(); c=client([hit({'00':3,'11':5}),hit({'01':8})])
    job=SamplerCache(sampler,c).run([circuit(),circuit()],shots=8)
    assert job.from_cache and not sampler.calls
    result=job.result()
    assert len(result)==2
    assert _joint_counts(circuit(),result[0].data,()) == {0:3,3:5}
    assert _joint_counts(circuit(),result[1].data,()) == {1:8}
    assert result[0].data.alpha.get_counts()=={'0':3,'1':5}
    assert result[0].metadata['osr']['shot_order']=='reconstructed_from_counts'

def test_parameter_sweep_shape_and_pub_shots():
    theta=Parameter('theta');qc=QuantumCircuit(1,1);qc.rx(theta,0);qc.measure(0,0)
    sampler=V2Sampler();c=client([hit({'0':3}),hit({'1':3})])
    result=SamplerCache(sampler,c).run([(qc,[[0.0],[3.14]],3)],shots=99).result()
    assert result[0].data.c.shape==(2,)
    assert result[0].data.c.get_counts(0)=={'0':3}
    assert result[0].data.c.get_counts(1)=={'1':3}
    calls=c.sample_cache.call_args_list
    assert calls[0].kwargs['circuit_hash']!=calls[1].kwargs['circuit_hash']
    assert calls[0].kwargs['shots']==3

def test_one_miss_delegates_entire_batch():
    sampler=V2Sampler();c=client([hit({'00':8}),{'hit':False}])
    job=SamplerCache(sampler,c,auto_store=False).run([circuit(),circuit()],shots=8)
    assert not job.from_cache
    assert len(sampler.calls[0][0])==2
    assert len(job.result())==2

def test_http_failure_delegates_and_autostores_once():
    sampler=V2Sampler();c=client([httpx.ConnectError('offline')]);c.store_circuit.return_value={'id':'circuit-id','circuit_hash':'a'*64};c.create_resource.return_value={'id':'execution-id'}
    job=SamplerCache(sampler,c).run(circuit(),shots=16)
    result=job.result();assert job.result() is result
    assert c.store_collection.call_count==1
    values=c.store_collection.call_args.args[0]
    assert sum(values.values())==16
    assert set(values)<= {0,3}
    assert c.store_collection.call_args.kwargs['metadata']['result_kind']=='hardware_counts'

def test_corrupt_cache_is_rejected():
    with pytest.raises(ValueError,match='cache response'):
        SamplerCache(V2Sampler(),client([hit({'00':7})])).run(circuit(),shots=8)

def test_callback_and_job_methods():
    backend=Mock();backend.result.return_value=object();callback=Mock()
    job=CachedJob(_backend_job=backend,_on_result=callback)
    assert job.result() is job.result()
    callback.assert_called_once()
    with pytest.raises(RuntimeError): CachedJob().result()

import ast
import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import server
from pipeline import PipelineWorker

class FakeWorker(PipelineWorker):
    def start(self): self.running=True; self.ready.set()
    def is_alive(self): return getattr(self,'running',False)

class AppTests(unittest.TestCase):
    def setUp(self):
        server.worker=None;server.owner=None;server.records.clear();server.events=queue.Queue()
        self.client=server.app.test_client()
        self.headers={'X-App-Request':'1'}
    def start(self):
        with patch.object(server,'PipelineWorker',FakeWorker):
            r=self.client.post('/api/start',json={'language':'Chinese'},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.headers['X-Session']=r.json['session']
    def test_single_session_and_access(self):
        self.start()
        self.assertEqual(self.client.post('/api/start',json={'language':'Chinese'},headers=self.headers).status_code,409)
        self.assertEqual(self.client.get('/api/state').status_code,403)
        self.assertEqual(self.client.get('/health',headers={'Host':'example.com'}).status_code,403)
        self.assertEqual(self.client.post('/api/stop',headers={**self.headers,'Origin':'https://other.example'}).status_code,403)
    def test_live_language_switch_without_restart(self):
        self.start()
        self.assertEqual(server.worker._target_language, 'Chinese')
        r=self.client.post('/api/language',json={'language':'Vietnamese'},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(server.worker._target_language, 'Vietnamese')
        state=self.client.get('/api/state',headers=self.headers).json
        self.assertEqual(state['language'], 'Vietnamese')

    def test_language_switch_rejects_invalid_target(self):
        self.start()
        self.assertEqual(self.client.post('/api/language',json={'language':'French'},headers=self.headers).status_code,400)

    def test_audio_validation_and_stop(self):
        self.start()
        for payload in (b'x',np.array([float('nan')],dtype='<f4').tobytes()):
            self.assertEqual(self.client.post('/api/audio',data=payload,headers=self.headers).status_code,400)
        data=np.zeros(480,dtype='<f4').tobytes()
        self.assertEqual(self.client.post('/api/audio',data=data,headers=self.headers).status_code,200)
        self.assertEqual(len(server.worker._audio),480)
        self.assertEqual(self.client.post('/api/stop',headers=self.headers).status_code,200)
        self.assertTrue(server.worker._capture_stop_event.is_set())
        self.assertEqual(self.client.post('/api/audio',data=data,headers=self.headers).status_code,409)
    def test_history_replaces_provisional(self):
        self.start()
        for text in ('Hello','Hello world'):
            server.events.put(('result',({'utterance_id':1,'corrected_english':text,'translation':'你好'},)))
        r=self.client.get('/api/state',headers=self.headers)
        self.assertEqual(len(r.json['records']),1)
        self.assertEqual(r.json['records'][0]['corrected_english'],'Hello world')
        self.assertIn('Hello world',self.client.get('/api/history',headers=self.headers).data.decode())
    def test_discard_removes_corrupt_caption_from_page_and_download(self):
        self.start()
        server.events.put(('result',({'utterance_id':1,'corrected_english':'20'+'%$'*30,'translation':'bad'},)))
        server.events.put(('discarded',(1,)))
        self.assertEqual(self.client.get('/api/state',headers=self.headers).json['records'],[])
        self.assertNotIn('%$',self.client.get('/api/history',headers=self.headers).data.decode())

    def test_backlog_is_explicit(self):
        self.start()
        server.worker._audio.extend([0]*server.worker._audio.maxlen)
        r=self.client.post('/api/audio',data=np.zeros(480,dtype='<f4').tobytes(),headers=self.headers)
        self.assertEqual(r.status_code,429)
    def test_word_guard(self):
        self.assertTrue(PipelineWorker._preserves_lexical_content('hello world','Hello, world.'))
        self.assertFalse(PipelineWorker._preserves_lexical_content('five options','four options'))
    def test_ui_and_health(self):
        with self.client.get('/') as response: self.assertEqual(response.status_code,200)
        with self.client.get('/static/capture.js') as response: self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/health').json,{'ok':True})

if __name__=='__main__':unittest.main()

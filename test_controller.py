import unittest
from controller import GestureGate

class GateTests(unittest.TestCase):
    def test_hold_and_release(self):
        g=GestureGate()
        self.assertIsNone(g.update('palm',.99,0,.8))
        self.assertIsNone(g.update('palm',.99,.35,.8))
        self.assertEqual(g.update('palm',.99,.75,.8),'palm')
        self.assertIsNone(g.update('palm',.99,2,.8))
        g.update('no_gesture',.99,2.1,.8)
        g.update('palm',.99,2.2,.8);g.update('palm',.99,2.6,.8)
        self.assertEqual(g.update('palm',.99,3,.8),'palm')
    def test_low_scores_and_stale_frames(self):
        g=GestureGate()
        for i in range(10):self.assertIsNone(g.update('like',.3,i*.3,.8))
        g.reset();g.update('like',.99,0,.8)
        self.assertIsNone(g.update('like',.99,3,.8))
    def test_jitter(self):
        g=GestureGate()
        for i in range(10):self.assertIsNone(g.update('palm' if i%2 else 'fist',.99,i*.3,.8))
    def test_cooldown(self):
        g=GestureGate(hold_seconds=.1,min_frames=2)
        g.update('palm',1,0,.8);self.assertEqual(g.update('palm',1,.2,.8),'palm')
        g.update('fist',1,.3,.8)
        self.assertIsNone(g.update('fist',1,.5,.8))
        self.assertEqual(g.update('fist',1,1.7,.8),'fist')

if __name__=='__main__':unittest.main()

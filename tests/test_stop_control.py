import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
from backend.stop_control import StopControl
P = NS(MAV_TYPE_SUBMARINE=12, MAV_AUTOPILOT_ARDUPILOTMEGA=3, MAV_COMP_ID_AUTOPILOT1=1,
       MAV_MODE_FLAG_SAFETY_ARMED=128, MAV_CMD_COMPONENT_ARM_DISARM=400,
       MAV_RESULT_ACCEPTED=0, MAV_RESULT_IN_PROGRESS=5)
def msg(kind='HEARTBEAT', system=1, component=1, **fields):
    values = dict(type=12, autopilot=3, base_mode=128); values.update(fields)
    return NS(get_type=lambda: kind, get_srcSystem=lambda: system,
              get_srcComponent=lambda: component, **values)
class StopTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.c = StopControl(P, lambda: self.now)
        self.conn = NS(mav=Mock(), source_system=255, source_component=191)
        self.c.attach(self.conn)
    def ready(self): self.c.observe(msg())
    def test_no_heartbeat_no_send(self):
        self.c.request('a'); self.conn.mav.command_long_send.assert_not_called()
        self.assertEqual(self.c.status['phase'], 'unconfirmed')
    def test_gcs_and_copter_cannot_select_target(self):
        self.c.observe(msg(type=6, autopilot=8, system=255))
        self.c.observe(msg(type=2)); self.assertIsNone(self.c.target)
    def test_normal_disarm_targets_detected_fc(self):
        self.c.observe(msg(system=42)); self.c.request('a')
        self.conn.mav.command_long_send.assert_called_once_with(42,1,400,0,0,0,0,0,0,0,0)
        self.assertEqual(self.c.status['phase'], 'pending')
    def test_ack_not_completion(self):
        self.ready(); self.c.request('a')
        self.c.observe(msg('COMMAND_ACK', command=400, result=0))
        self.assertEqual(self.c.status['phase'], 'pending')
        self.c.observe(msg(base_mode=0)); self.assertEqual(self.c.status['phase'], 'confirmed')
    def test_other_source_or_recipient_ignored(self):
        self.ready(); self.c.request('a')
        self.c.observe(msg(system=2, base_mode=0)); self.c.observe(msg(component=100, base_mode=0))
        self.c.observe(msg('COMMAND_ACK', command=400, result=2, target_component=190))
        self.assertEqual(self.c.status['phase'], 'pending')
    def test_denied_no_retry(self):
        self.ready(); self.c.request('a'); self.c.observe(msg('COMMAND_ACK', command=400, result=2))
        self.now += 1.1; self.c.tick()
        self.assertEqual(self.c.status['phase'], 'rejected')
        self.assertEqual(self.conn.mav.command_long_send.call_count, 1)
    def test_bounded_retries_timeout(self):
        self.ready(); self.c.request('a')
        for _ in range(6): self.now += 1.01; self.ready(); self.c.tick()
        self.assertEqual(self.conn.mav.command_long_send.call_count, 3)
        self.assertEqual(self.c.status['phase'], 'unconfirmed')
    def test_heartbeat_loss_and_no_replay(self):
        self.ready(); self.c.request('a'); self.now += 3.1; self.c.tick()
        self.assertIsNone(self.c.telemetry()['armed'])
        self.assertEqual(self.c.status['phase'], 'unconfirmed')
        self.ready(); self.c.tick(); self.assertEqual(self.conn.mav.command_long_send.call_count, 1)
    def test_duplicate_parallel_requests_coalesced(self):
        self.ready(); self.c.request('a'); self.c.request('a'); self.c.request('b')
        self.assertEqual(self.conn.mav.command_long_send.call_count, 1)
        self.assertEqual(self.c.status['id'], 'a')
    def test_already_disarmed(self):
        self.c.observe(msg(base_mode=0)); self.c.request('a')
        self.conn.mav.command_long_send.assert_not_called()
        self.assertEqual(self.c.status['phase'], 'confirmed')
    def test_send_failure_and_reconnect(self):
        self.ready(); self.conn.mav.command_long_send.side_effect = OSError('disconnected')
        self.c.request('a'); self.assertEqual(self.c.status['phase'], 'unconfirmed')
        self.c.disconnect(); self.c.attach(self.conn)
        self.assertIsNone(self.c.telemetry()['armed']); self.assertFalse(self.c.fresh())
    def test_disconnect_pending(self):
        self.ready(); self.c.request('a'); self.c.disconnect()
        self.assertEqual(self.c.status['phase'], 'unconfirmed')
        self.assertFalse(self.c.telemetry()['stop_available'])
    def test_invalid_id(self):
        self.ready()
        for value in (None, {}, '', 'x'*81): self.assertIn('error', self.c.request(value))
        self.conn.mav.command_long_send.assert_not_called()
if __name__ == '__main__': unittest.main()

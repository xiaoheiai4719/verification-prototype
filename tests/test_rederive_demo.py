import json
import tempfile
import unittest
from pathlib import Path

import rederive
import verify


class RederiveDemoTests(unittest.TestCase):
    def test_same_card_and_actual_fake_storage_results(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            report = verify.demo(out)
            card, = report['decision_cards']
            session = rederive.start_session(report, card)
            view = rederive.public_view(report, card, session)
            self.assertNotIn('reveal', view)
            session = rederive.answer(session, '保留操作标识并检查外部契约')
            session = rederive.hint(report, card, session)
            hint = rederive.public_view(report, card, session)
            self.assertEqual(len(hint['hints']), 1)
            self.assertNotIn('reveal', hint)
            session = rederive.reveal(report, card, session)
            reveal = rederive.public_view(report, card, session)['reveal']
            self.assertEqual({'baseline': 'failed', 'fixed': 'passed'}, {
                row['variant']: row['status'] for row in reveal['test_status']['runs']
            })
            self.assertEqual(reveal['business_acceptance'], 'not_accepted')
            self.assertIn('24 小时', reveal['unknowns'][0])
            self.assertIn('def put', reveal['references'][0]['quote'])
            page = (out / 'learn.html').read_text(encoding='utf-8')
            payload = page.split('<script type="application/json" id="lesson-data">')[1].split('</script>')[0]
            self.assertEqual(json.loads(payload)['reveal'], reveal)

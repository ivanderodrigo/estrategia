import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class HistoryGapTest(unittest.TestCase):
    def test_consistent_counts(self):
        base = ROOT / 'data/public/historical'
        info = json.loads((base / 'gap_summary.json').read_text(encoding='utf-8'))
        data = json.loads((base / 'gap_matches.json').read_text(encoding='utf-8'))
        self.assertEqual(info['tasks_with_historical_antecedents'], len(data['matches']))
        self.assertEqual(info['tasks_with_historical_antecedents'] + info['tasks_without_exact_name_field_history'], info['total_current_research_tasks'])
        self.assertTrue(all(row['status'] == 'HISTORICAL_RESEARCH_LEAD_NOT_VERIFIED' for row in data['matches']))

if __name__ == '__main__':
    unittest.main()

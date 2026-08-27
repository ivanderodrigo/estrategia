import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from v31.taxonomy import classify_record
assert classify_record({'title':'AttackIQ Awards recognize customers','url':'https://attackiq.com/awards'}).classification != 'procurement_award'
assert classify_record({'title':'Contract award notice','contracting_authority':'Ayuntamiento','notice_id':'X','cpv':'48000000','url':'https://ted.europa.eu/x'}).classification == 'procurement_award'
print('SMOKE OK · Awards guard + procurement anchors')

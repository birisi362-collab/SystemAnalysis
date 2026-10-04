import unittest
from app.models import FinalModel, Connection
from app.renderer import render_dot, render_mermaid
from app.validator_audit import baseline

class ConnectionDirectionTests(unittest.TestCase):
    def test_old_records_remain_one_way(self):
        e=Connection(id='E',source='A',target='B')
        self.assertEqual(e.direction,'unidirectional')

    def test_bidirectional_export_preserves_two_arrowheads(self):
        data=baseline();data['architecture']['connections'][0]['direction']='bidirectional'
        final=FinalModel.model_validate(data)
        self.assertIn('<-->',render_mermaid(final))
        self.assertIn('dir=both',render_dot(final))
        self.assertEqual(FinalModel.model_validate_json(final.model_dump_json()).architecture.connections[0].direction,'bidirectional')

    def test_parallel_and_reverse_connections_are_preserved_in_exports(self):
        data=baseline();data['architecture']['connections'] += [
            dict(id='E2',source='A',target='B',type='control',protocol='RS422'),
            dict(id='E3',source='B',target='A',type='data',protocol='Ethernet')]
        final=FinalModel.model_validate(data)
        mmd=render_mermaid(final)
        self.assertEqual(mmd.count('-->'),3)
        self.assertIn('n1 -->',mmd)
        self.assertIn('RS422',mmd)
        self.assertIn('Ethernet',mmd)

if __name__=='__main__':unittest.main()

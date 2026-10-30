import unittest
from wheel.pr_review import verdict,publish,MARKER,body

class ReviewTests(unittest.TestCase):
    def test_verdicts_and_missing_trials(self):
        rows=[{'trial':i,'world':w,'oracle_pass':w=='base'} for i in range(3) for w in ['base','candidate']]
        self.assertEqual(verdict(rows),'reproduced_regression')
        self.assertEqual(verdict(rows[:-1]),'inconclusive')
        for r in rows:r['oracle_pass']=True
        self.assertEqual(verdict(rows),'not_reproduced')
    def test_update_and_stale(self):
        calls=[]
        def api(method,path,data=None):
            calls.append((method,path,data))
            if path.startswith('/pulls/'):return {'state':'open','base':{'sha':'base'},'head':{'sha':'new'}}
            if path.startswith('/issues/1/comments?'):return [{'id':9,'body':MARKER,'user':{'login':'github-actions[bot]'}}]
            if path=='/user':return {'login':'github-actions[bot]'}
            return {'id':9}
        result=publish(api,1,{'base':'base','head':'old','status':'reproduced_regression'},'https://github.com/run')
        self.assertEqual(result['status'],'stale')
        self.assertEqual(calls[-1][0],'PATCH')
        self.assertNotIn('Result: reproduced_regression',calls[-1][2]['body'])
    def test_unsupported_never_claims_execution(self):
        text=body({'base':'b','head':'h','status':'unsupported'},'url')
        self.assertIn('not executed',text)
        self.assertNotIn('fresh deterministic',text)
    def test_permission_failure_propagates(self):
        def api(*args):raise PermissionError()
        with self.assertRaises(PermissionError):publish(api,1,{},'url')

if __name__=='__main__':unittest.main()

import unittest
from app import calculate

class ModelTests(unittest.TestCase):
    def test_example(self):
        r=calculate(1.23,.2557,.30,.065,.05,.03,.0111)
        for k,v in {'beta':1.6223524285714286,'ke_us':.15545290785714286,'kd_us':.0611,'wacc_us':.1224600545,'ke_local':.13344428104081633,'kd_local':.04088857142857143,'wacc_local':.10254100584285714}.items(): self.assertAlmostEqual(r[k],v,12)
    def test_equal_yields(self):
        for m in ['Parity','Local CAPM']:
            r=calculate(1.23,.2557,.3,.065,.05,.05,.0111,method=m)
            for k in ['ke','kd','wacc']: self.assertAlmostEqual(r[k+'_us'],r[k+'_local'],12)
    def test_zero_debt(self):
        for m in ['Parity','Local CAPM']:
            r=calculate(1.23,.2557,0,.065,.05,.03,.0111,method=m)
            for k in ['us','local']: self.assertAlmostEqual(r['ke_'+k],r['wacc_'+k],12)
    def test_override(self):
        for m in ['Parity','Local CAPM']:
            a=calculate(1.23,.2557,.3,.065,.05,.03,.0111,method=m); b=calculate(1.23,.2557,.3,.065,.05,.03,.0111,.02,method=m)
            for k in ['ke_us','kd_us','wacc_us','ke_local']: self.assertEqual(a[k],b[k])
            self.assertNotEqual(a['wacc_local'],b['wacc_local'])

if __name__=='__main__': unittest.main()

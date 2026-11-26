"""Offline closed-form tests of the original Fincept optimizer."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"fincept-qt/scripts"))
import optimize_portfolio_weights as opt

class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.mu=np.array([.08,.12])
        self.cov=np.diag([.04,.16])

    def solve(self,method,extra=None):
        out=opt.run_strategy(method,self.mu,self.cov,2,extra=extra)
        self.assertNotIn("error",out)
        w=out["weights"]
        self.assertTrue(np.all(np.isfinite(w)))
        self.assertTrue(np.all(w>=0))
        self.assertAlmostEqual(float(w.sum()),1,places=10)
        self.assertAlmostEqual(out["return"],float(w@self.mu),places=10)
        self.assertAlmostEqual(out["volatility"],float(np.sqrt(w@self.cov@w)),places=10)
        return w

    def test_closed_form(self):
        for method,expected in (("min_volatility",[.8,.2]),("risk_parity",[2/3,1/3]),
                                ("max_sharpe",[2/3,1/3]),("equal_weight",[.5,.5]),
                                ("max_return",[0,1]),("target_return",[.5,.5])):
            with self.subTest(method=method):
                np.testing.assert_allclose(self.solve(method),expected,rtol=0,atol=2e-5)

    def test_annualization(self):
        x=pd.DataFrame([[.01,.02],[-.01,.04],[.03,-.02]])
        mu,cov,n=opt.build_params(x)
        np.testing.assert_allclose(mu,[2.52,3.36],rtol=0,atol=1e-12)
        np.testing.assert_allclose(cov,np.array([[.0004,-.0006],[-.0006,.0009333333333333333]])*252,rtol=0,atol=1e-12)
        self.assertEqual(n,2)

    def test_infeasible_target_denied(self):
        out=opt.run_strategy("target_return",self.mu,self.cov,2,extra={"target_return":.50})
        self.assertIn("error",out)

    def test_solver_failure_denied(self):
        with patch("scipy.optimize.minimize",return_value=SimpleNamespace(success=False,x=np.array([.5,.5]),fun=.2)):
            self.assertIn("error",opt.run_strategy("min_volatility",self.mu,self.cov,2))

    def test_frontier_solver_failure_denied(self):
        with patch("scipy.optimize.minimize",return_value=SimpleNamespace(success=False,x=np.array([.5,.5]),fun=.2)):
            self.assertEqual(opt.build_frontier(self.mu,self.cov,2,num_points=5),[])

    def test_frontier_negative_returns_and_endpoint(self):
        for mu in (self.mu,np.array([-.12,-.08])):
            pts=opt.build_frontier(mu,self.cov,2,num_points=9)
            self.assertEqual(len(pts),9)
            self.assertAlmostEqual(pts[0]["return"],float(np.array([.8,.2])@mu),places=6)
            self.assertAlmostEqual(pts[-1]["return"],float(mu.max()),places=6)
            for pt in pts:
                w=(pt["return"]-mu[1])/(mu[0]-mu[1])
                self.assertGreaterEqual(w,-1e-6)
                self.assertLessEqual(w,1+1e-6)
                self.assertAlmostEqual(pt["volatility"],float(np.sqrt(np.array([w,1-w])@self.cov@np.array([w,1-w]))),places=7)

if __name__=="__main__":
    unittest.main()

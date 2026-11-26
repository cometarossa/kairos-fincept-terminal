"""Portfolio covariance and Euler-risk boundary tests (synthetic only)."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"fincept-qt/scripts"))
import optimize_portfolio_weights as opt

class RiskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.mu=np.array([.08,.12])
        self.cov=np.diag([.04,.16])

    def test_bad_covariance_denied_before_solver(self):
        for cov in (np.array([[.04,.2],[.2,.16]]),
                    np.array([[.04,.01],[.02,.16]]),
                    np.array([[.04,np.nan],[np.nan,.16]]),
                    np.array([[.04,.04],[.04,.04]]),
                    np.array([[0.,0.],[0.,.16]]), np.eye(3)):
            with self.subTest(cov=cov),patch("scipy.optimize.minimize") as solve:
                self.assertIn("error",opt.run_strategy("min_volatility",self.mu,cov,2))
                self.assertEqual(opt.build_frontier(self.mu,cov,2),[])
                solve.assert_not_called()

    def test_bad_mean_and_unknown_method(self):
        for mu,n in ((np.array([np.inf,.12]),2),(np.array([.08]),2),(self.mu,True),(self.mu,0)):
            self.assertIn("error",opt.run_strategy("equal_weight",mu,self.cov,n))
        self.assertIn("error",opt.run_strategy("typo",self.mu,self.cov,2))

    def test_return_panel_rejects_missing_or_duplicate(self):
        for panel in (pd.DataFrame([[.01,.02],[.03,np.nan],[.04,.05]]),
                      pd.DataFrame([[.01,.02],[.03,.04],[.04,.05]],columns=["A","A"]),
                      pd.DataFrame([[.01,.02],[.03,.04],[.04,.05]],index=[0,0,1])):
            with self.assertRaises(ValueError):
                opt.build_params(panel)

    def test_risk_parity_residual_denied(self):
        with patch("scipy.optimize.minimize",return_value=SimpleNamespace(success=True,x=np.array([.5,.5]))):
            self.assertIn("error",opt.run_strategy("risk_parity",self.mu,self.cov,2))

    def test_euler_decomposition_and_negative_contribution(self):
        # SPD with negative covariance; the second asset hedges the first.
        cov=np.array([[.04,-.03],[-.03,.09]])
        w=np.array([.9,.1])
        out=opt.risk_decomposition(w,cov)
        var=.81*.04+2*.9*.1*(-.03)+.01*.09
        self.assertAlmostEqual(out["volatility"],var**.5,places=12)
        expected=np.array([.9*(.9*.04-.1*.03),.1*(-.9*.03+.1*.09)])/var
        np.testing.assert_allclose(out["percentage"],100*expected,rtol=0,atol=1e-10)
        self.assertLess(out["percentage"][1],0)
        self.assertAlmostEqual(sum(out["percentage"]),100,places=10)
        self.assertAlmostEqual(sum(out["component"]),out["volatility"],places=12)
        with self.assertRaises(ValueError):
            opt.risk_decomposition(np.array([.9,.9]),cov)

    def test_proxy_labels(self):
        a=opt.run_strategy("hrp",self.mu,self.cov,2)
        self.assertEqual(a["methodology"],"INVERSE_VARIANCE_PROXY")
        np.testing.assert_allclose(a["weights"],[.8,.2])
        b=opt.run_strategy("black_litterman",self.mu,self.cov,2)
        self.assertEqual(b["methodology"],"EQUILIBRIUM_PRIOR_NO_VIEWS")

if __name__=="__main__":
    unittest.main()

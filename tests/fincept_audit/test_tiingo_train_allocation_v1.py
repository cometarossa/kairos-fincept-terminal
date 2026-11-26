"""Independent diagnostic oracle and fixed admission regression."""
import unittest
from unittest.mock import patch
import numpy as np
from research.kairos_bridge_v1 import tiingo_train_allocation_v1 as a

class AllocationTests(unittest.TestCase):
    def test_bad_input_before_import_or_compute(self):
        for raw,plan in ((None,b"{}"),(b"{}",b"{}"),(b"x"*200001,b"{}")):
            with patch.object(a,"exact_moments") as compute:
                with self.assertRaises(ValueError):
                    a.run(raw,plan)
                compute.assert_not_called()

    def test_diagonal_closed_form(self):
        mu=np.array([.08,.12,.16]);cov=np.diag([.04,.16,.36])
        for method,expected in (
                ("min_volatility",np.array([25.,6.25,1/.36])),
                ("max_sharpe",np.array([1.,.5,1/3])),
                ("risk_parity",np.array([5.,2.5,1/.6]))):
            w=a.independent_weights(method,mu,cov)
            np.testing.assert_allclose(w,expected/expected.sum(),atol=1e-10,rtol=0)

    def test_all_negative_excess(self):
        mu=np.array([-.02,-.05,-.10]);cov=np.diag([.04,.16,.36])
        np.testing.assert_array_equal(a.independent_weights("max_sharpe",mu,cov),[0,1,0])

    def test_risk_sums(self):
        mu=np.array([.08,.12,.16]);cov=np.diag([.04,.16,.36])
        w=a.independent_weights("risk_parity",mu,cov)
        _,_,_,risk=a.metrics(w,mu,cov)
        np.testing.assert_allclose(risk,[100/3]*3,atol=1e-7,rtol=0)

if __name__=="__main__":
    unittest.main()

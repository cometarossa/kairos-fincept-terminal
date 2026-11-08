import unittest
from tools.fincept_authority.server_policy import authorize, catalog

class PolicyTests(unittest.TestCase):
    def test_known_quant(self): self.assertTrue(authorize("synthetic-researcher","quant.volatility.read").allowed)
    def test_reviewer_cannot_quant(self): self.assertEqual(authorize("synthetic-reviewer","quant.volatility.read").code,"FORBIDDEN")
    def test_unknown_identity(self): self.assertEqual(authorize("unknown","market.fixture.read").code,"UNAUTHENTICATED")
    def test_unknown_tool(self): self.assertFalse(authorize("synthetic-researcher","quant.unlisted.read").allowed)
    def test_forged_scope(self): self.assertFalse(authorize("synthetic-reviewer","quant.volatility.read",request={"scopes":["*"],"admin":True}).allowed)
    def test_forged_identity_request(self): self.assertFalse(authorize("unknown","market.fixture.read",request={"principal":"synthetic-researcher"}).allowed)
    def test_forbidden_routes(self):
        for name in ("broker.place_order","security.reset","order.cancel","risk.override","deployment.start","account.keys"):
            with self.subTest(name=name): self.assertFalse(authorize("synthetic-researcher",name).allowed)
    def test_catalog(self): self.assertEqual(catalog("synthetic-reviewer"),("market.fixture.read",))
    def test_unknown_catalog(self): self.assertEqual(catalog("unknown"),())
    def test_no_external_authority(self): self.assertFalse(authorize("synthetic-researcher","broker.place_order",request={"approved":True}).allowed)
if __name__=="__main__": unittest.main()

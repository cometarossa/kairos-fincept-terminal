"""Fixed synthetic child; TLS modes only connect to ephemeral local fixture."""
import sys
import time
if __name__ == "__main__":
    if len(sys.argv)!=2:sys.exit(2)
    if sys.argv[1]=="success":sys.exit(0)
    if sys.argv[1]=="failure":sys.exit(3)
    if sys.argv[1]=="stall":time.sleep(30);sys.exit(4)
    if sys.argv[1] in ("tls_success","tls_rate_limit","tls_invalid"):
        from pathlib import Path
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from twelve_fx_e2e_worker_qa_v1 import run_fixture
        sys.exit(run_fixture(sys.argv[1]))
    sys.exit(2)

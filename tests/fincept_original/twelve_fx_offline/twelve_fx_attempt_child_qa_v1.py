"""Fixed no-network synthetic child; not a provider connector."""
import sys
import time
if __name__ == "__main__":
    if len(sys.argv)!=2:sys.exit(2)
    if sys.argv[1]=="success":sys.exit(0)
    if sys.argv[1]=="failure":sys.exit(3)
    if sys.argv[1]=="stall":time.sleep(30);sys.exit(4)
    sys.exit(2)

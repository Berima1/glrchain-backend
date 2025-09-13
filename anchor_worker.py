"""Anchor worker template - in prod use KMS/HSM to sign txs."""
import os
from web3 import Web3
RPC = os.getenv('ANCHOR_RPC_URL')
if RPC:
    w3 = Web3(Web3.HTTPProvider(RPC))
    print('web3 connected', w3.isConnected())
else:
    print('Set ANCHOR_RPC_URL')

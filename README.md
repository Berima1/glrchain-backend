GLRChain Backend (Heavyweight) - MLNR

This package contains a production-minded FastAPI backend scaffold with anti-galamsey modules.

Upload this package to a new GitHub repo and connect to Render/Railway for deployment (no heavy local storage needed).

Essential env variables:
DATABASE_URL
SECRET_KEY
ANCHOR_RPC_URL
IPFS_PINATA_KEY
IPFS_PINATA_SECRET
KMS_ARN (optional)

Security: Use KMS/HSM for private keys; do not store secrets in repo.

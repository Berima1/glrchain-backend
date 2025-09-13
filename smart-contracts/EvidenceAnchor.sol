// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
contract EvidenceAnchor {
    event EvidenceAnchored(bytes32 indexed evidenceHash, string cid, address indexed reporter);
    function anchorEvidence(bytes32 evidenceHash, string calldata cid) external {
        emit EvidenceAnchored(evidenceHash, cid, msg.sender);
    }
}

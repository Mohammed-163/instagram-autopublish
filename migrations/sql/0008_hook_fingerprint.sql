-- Phase 4 Part 2 -- Hook Fingerprint Additions

ALTER TABLE hook_structures
ADD COLUMN IF NOT EXISTS structural_fingerprint TEXT,
ADD COLUMN IF NOT EXISTS feature_fingerprint TEXT,
ADD COLUMN IF NOT EXISTS fingerprint_hash TEXT;

-- Create indexes for fast lookup based on structure or exact match
CREATE INDEX IF NOT EXISTS idx_hook_structures_structural_fingerprint ON hook_structures(structural_fingerprint);
CREATE INDEX IF NOT EXISTS idx_hook_structures_fingerprint_hash ON hook_structures(fingerprint_hash);

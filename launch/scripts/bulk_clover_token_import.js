#!/usr/bin/env node
/**
 * Bulk Clover token onboarding.
 *
 * For each (merchant_name, token) pair:
 *   1. Calls Clover /v3/merchants/current to discover the Clover merchant_id
 *   2. Finds our internal merchant in DB by fuzzy-matching business_name
 *   3. Encrypts the token with the dashboard's crypto lib
 *   4. UPDATEs merchants.clover_access_token + clover_merchant_id
 *   5. Reports per-row status (✅ saved / ⚠️ name mismatch / ❌ token bad)
 *
 * Run:
 *   cd ~/Documents/brain/infinity-pay-dashboard
 *   DATABASE_URL=postgresql://... ENCRYPTION_KEY=... node bulk_clover_token_import.js
 *
 * Or via Railway:
 *   railway run -- node /path/to/bulk_clover_token_import.js
 *
 * Idempotent: re-running with the same token + name updates the same row.
 */

const { Pool } = require('pg')
const { encryptMaybe } = require('./src/lib/crypto')

const CLOVER_BASE = process.env.CLOVER_ENV === 'sandbox'
  ? 'https://sandbox.dev.clover.com'
  : 'https://api.clover.com'

// ── INPUT — merchant name + Clover access token ────────────────────────────
const INPUTS = [
  { name: 'taku food',            token: '<TOKEN_REDACTED>' },
  { name: 'farhod food',          token: '<TOKEN_REDACTED>' },
  { name: 'shawarma #1',          token: '<TOKEN_REDACTED>' },
  { name: 'bison halal burger',   token: '<TOKEN_REDACTED>' },
  { name: 'silk road restaurant', token: '<TOKEN_REDACTED>' },
  { name: 'ochag bar and grill',  token: '<TOKEN_REDACTED>' },
  { name: 'faiza chicago',        token: '<TOKEN_REDACTED>' },
  { name: 'shawarma stop',        token: '<TOKEN_REDACTED>' },
]

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
})

async function fetchCloverMerchant(token) {
  const r = await fetch(`${CLOVER_BASE}/v3/merchants/current`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok) throw new Error(`Clover ${r.status}: ${await r.text().then(s => s.slice(0, 100))}`)
  return r.json()
}

async function findOurMerchantByName(name) {
  // Fuzzy: exact match → ILIKE wildcard → trigram-style word match
  const q = name.trim().toLowerCase()
  const exactSql = `SELECT id, business_name, mid, merchant_code FROM merchants WHERE LOWER(business_name) = $1 LIMIT 1`
  const ilikeSql = `SELECT id, business_name, mid, merchant_code FROM merchants WHERE LOWER(business_name) LIKE $1 ORDER BY LENGTH(business_name) ASC LIMIT 5`

  let { rows } = await pool.query(exactSql, [q])
  if (rows.length) return { match: rows[0], candidates: [] }

  // Try removing #N / numbers (e.g. "shawarma #1" → "shawarma")
  const cleaned = q.replace(/#\d+/g, '').replace(/\s+/g, ' ').trim()
  ;({ rows } = await pool.query(ilikeSql, [`%${cleaned}%`]))
  if (rows.length === 1) return { match: rows[0], candidates: [] }
  if (rows.length > 1)   return { match: null, candidates: rows }

  // Last resort: split on words, match if ANY word is in business_name
  const words = cleaned.split(' ').filter(w => w.length > 2)
  if (words.length === 0) return { match: null, candidates: [] }
  const wordPatterns = words.map((_, i) => `LOWER(business_name) LIKE $${i + 1}`).join(' AND ')
  const args = words.map(w => `%${w}%`)
  ;({ rows } = await pool.query(
    `SELECT id, business_name, mid, merchant_code FROM merchants WHERE ${wordPatterns} ORDER BY LENGTH(business_name) ASC LIMIT 5`,
    args
  ))
  return { match: rows.length === 1 ? rows[0] : null, candidates: rows.length > 1 ? rows : [] }
}

async function saveToken(merchantUuid, cloverMid, token) {
  const enc = encryptMaybe(token)
  await pool.query(
    `UPDATE merchants
       SET clover_access_token = $1,
           clover_merchant_id  = $2,
           clover_connected_at = NOW()
     WHERE id = $3`,
    [enc, cloverMid, merchantUuid]
  )
}

async function processOne(input) {
  const { name, token } = input
  // 1. Verify token + get Clover merchant info
  let cloverInfo
  try {
    cloverInfo = await fetchCloverMerchant(token)
  } catch (e) {
    return { name, status: '❌ TOKEN_INVALID', error: e.message }
  }
  const cloverMid  = cloverInfo.id
  const cloverName = cloverInfo.name

  // 2. Find our merchant
  const { match, candidates } = await findOurMerchantByName(name)
  if (!match) {
    if (candidates.length > 0) {
      return {
        name,
        status: '⚠️ AMBIGUOUS',
        cloverName,
        cloverMid,
        candidates: candidates.map(c => `${c.merchant_code || '—'} ${c.business_name}`).join(' | '),
      }
    }
    return { name, status: '⚠️ NOT_IN_DB', cloverName, cloverMid }
  }

  // 3. Save
  try {
    await saveToken(match.id, cloverMid, token)
    return {
      name,
      status: '✅ SAVED',
      cloverName,
      cloverMid,
      ourMerchant: `${match.merchant_code || '—'} ${match.business_name}`,
    }
  } catch (e) {
    return { name, status: '❌ SAVE_FAILED', error: e.message }
  }
}

async function main() {
  if (!process.env.DATABASE_URL) {
    console.error('DATABASE_URL is required')
    process.exit(2)
  }
  if (!process.env.ENCRYPTION_KEY) {
    console.error('ENCRYPTION_KEY is required (encrypts the token before saving)')
    process.exit(2)
  }

  console.log(`\n🔌 Bulk Clover token import — ${INPUTS.length} merchants\n`)
  console.log('─'.repeat(80))
  const results = []
  for (const input of INPUTS) {
    process.stdout.write(`→ ${input.name.padEnd(28)} `)
    const res = await processOne(input)
    results.push(res)
    if (res.status.startsWith('✅')) {
      console.log(`${res.status}  Clover: ${res.cloverName} (${res.cloverMid})`)
      console.log(`  ${' '.repeat(28)} → ${res.ourMerchant}`)
    } else if (res.status.startsWith('⚠️ AMBIGUOUS')) {
      console.log(res.status)
      console.log(`  ${' '.repeat(28)}   Clover: ${res.cloverName} (${res.cloverMid})`)
      console.log(`  ${' '.repeat(28)}   our DB candidates: ${res.candidates}`)
    } else if (res.status.startsWith('⚠️ NOT_IN_DB')) {
      console.log(`${res.status}  Clover: ${res.cloverName} (${res.cloverMid})  — нет в БД`)
    } else {
      console.log(`${res.status}  ${res.error || ''}`)
    }
  }

  console.log('─'.repeat(80))
  const ok = results.filter(r => r.status.startsWith('✅')).length
  const amb = results.filter(r => r.status.startsWith('⚠️ AMBIGUOUS')).length
  const notInDb = results.filter(r => r.status.startsWith('⚠️ NOT_IN_DB')).length
  const fail = results.filter(r => r.status.startsWith('❌')).length
  console.log(`\nИтого: ✅ ${ok} saved · ⚠️ ${amb} ambiguous · ⚠️ ${notInDb} not in DB · ❌ ${fail} failed`)

  await pool.end()
}

main().catch(e => { console.error(e); process.exit(1) })

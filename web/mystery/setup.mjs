#!/usr/bin/env node
// Configures a mystery6 checkout as a read-only browser for BFF's live
// database. BFF owns this script; mystery6 stays generic. Invoked by the
// /web command against a dedicated, disposable clone (web/mystery/app/) —
// never against a personal dev checkout.
//
// Usage: node web/mystery/setup.mjs <clone-root> [port]

import { existsSync, readFileSync, writeFileSync, copyFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { randomBytes } from 'crypto';
import Database from 'better-sqlite3';
import bcrypt from 'bcryptjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BFF_ROOT = resolve(__dirname, '..', '..');

const cloneRoot = process.argv[2] ? resolve(process.argv[2]) : resolve(BFF_ROOT, 'web', 'mystery', 'app');
const port = process.argv[3] || '3071';

const schemaPath = resolve(cloneRoot, 'src', 'db', 'schema.js');
if (!existsSync(schemaPath)) {
  console.error(`Error: mystery6 checkout not found at ${cloneRoot} (missing src/db/schema.js)`);
  process.exit(1);
}
const { applySchema } = await import(schemaPath);

// Live BFF database — never copied. This deployment is read-only at the
// permission layer; all writes to this file must continue to go through
// BFF's own sanctioned scripts. BFF_DATA_DIR (same override db.py honors)
// lets /web point at a throwaway/demo dataset -- e.g. the UAT fixture --
// instead of the real data/ directory. mystery-config.db (the admin/login
// config for this web UI instance, not BFF's own data) intentionally stays
// pinned to the real data/ regardless -- it's fine, and preferable, for a
// demo run to reuse the same login rather than re-provisioning one.
const bffDataDir  = process.env.BFF_DATA_DIR || resolve(BFF_ROOT, 'data');
const bffDbPath   = resolve(bffDataDir, 'best_foot_forward.db');
const configDest  = resolve(BFF_ROOT, 'data', 'mystery-config.db');
const envDest     = resolve(cloneRoot, '.env');

if (!existsSync(bffDbPath)) {
  console.error(`Error: BFF database not found at ${bffDbPath}`);
  process.exit(1);
}

if (existsSync(configDest)) {
  console.log('  Reusing existing data/mystery-config.db');
} else {
  const db = new Database(configDest);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  applySchema(db);
  console.log('  Created data/mystery-config.db');

  // Groups. Administrators (group_id 1) is required by schema convention but
  // deliberately has no user assigned — nobody gets the always-full-access
  // bypass in mystery6's permission-service.js for this deployment.
  db.prepare(`INSERT INTO groups (group_id, group_name, group_desc) VALUES (1, 'Administrators', 'Full system access (unused for BFF)')`).run();
  db.prepare(`INSERT INTO groups (group_name, group_desc) VALUES ('Viewers', 'Read-only access to all BFF tables')`).run();
  const viewersGroupId = db.prepare(`SELECT group_id FROM groups WHERE group_name = 'Viewers'`).get().group_id;

  // Single read-only user.
  const bffHash = bcrypt.hashSync('bff', 12);
  const bffRow = db.prepare(
    `INSERT INTO users (user_username, user_email, user_password, user_first_name, user_last_name, password_is_default)
     VALUES ('bff', 'bff@localhost', ?, 'BFF', 'Viewer', 0)`
  ).run(bffHash);
  db.prepare(`INSERT INTO users_groups (user_id, group_id) VALUES (?, ?)`).run(bffRow.lastInsertRowid, viewersGroupId);
  console.log('  Created user: bff/bff (read-only viewer)');

  // Table definitions
  // [realName, displayName, pk, orderField, reverseSort, displayFields, dataWord]
  const tableDefs = [
    ['jds',           'Job Descriptions', 'id', 'company',       0, 'company,role,score,evaluated_at,lead_status',        'Job Description'],
    ['applications',  'Applications',     'id', 'applied_at',    1, 'jd_id,status,stage,applied_at,follow_up_date',       'Application'],
    ['employers',     'Employers',        'id', 'sort_order',    0, 'name,location,start_date,end_date',                  'Employer'],
    ['bullets',       'Bullets',          'id', 'employer_id',   0, 'employer_id,role,text',                              'Bullet'],
    ['skills',        'Skills',           'id', 'label',         0, 'label,content',                                      'Skill'],
    ['stories',       'Stories',          'id', 'title',         0, 'title,employer_id,readiness,timeframe',              'Story'],
    ['contacts',      'Contacts',         'id', 'interview_date',0, 'name,title,jd_id,interview_date,interview_stage',    'Contact'],
    ['assessments',   'Assessments',      'id', 'deadline',      0, 'type,application_id,deadline,submitted_at',          'Assessment'],
    ['education',     'Education',        'id', 'sort_order',    0, 'institution,degree,location',                        'Education'],
    ['file_registry', 'Files',            'id', 'registered_at', 1, 'file_type,file_path,jd_id,application_id,story_id',  'File'],
  ];

  const tableIds = {};
  for (const [realName, displayName, pk, orderField, reverseSort, displayFields, dataWord] of tableDefs) {
    const row = db.prepare(
      `INSERT INTO tables (table_real_name, table_display_name, table_primary_key, table_default_order_field,
                           table_default_reverse_sort, table_default_display_fields, table_display_data_word)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    ).run(realName, displayName, pk, orderField, reverseSort, displayFields, dataWord);
    tableIds[realName] = Number(row.lastInsertRowid);
  }
  console.log(`  Registered ${tableDefs.length} tables`);

  // Viewer permissions — select-only on every table.
  for (const tableId of Object.values(tableIds)) {
    db.prepare(
      `INSERT INTO groups_tables (group_id, table_id, select_access, insert_access, update_access, delete_access)
       VALUES (?, ?, 1, 0, 0, 0)`
    ).run(viewersGroupId, tableId);
  }
  console.log('  Set read-only permissions for Viewers group');

  // Foreign key relationships
  const fkDefs = [
    // [localTable, localField, foreignTable, valueField, labelField]
    ['applications',  'jd_id',          'jds',          'id', 'company,role'],
    ['bullets',       'employer_id',    'employers',    'id', 'name'],
    ['stories',       'employer_id',    'employers',    'id', 'name'],
    ['contacts',      'jd_id',          'jds',          'id', 'company,role'],
    ['assessments',   'application_id', 'applications', 'id', 'status,applied_at'],
    ['file_registry', 'jd_id',          'jds',          'id', 'company,role'],
    ['file_registry', 'application_id', 'applications', 'id', 'status,applied_at'],
    ['file_registry', 'story_id',       'stories',      'id', 'title'],
  ];

  for (const [local, localField, foreign, valueField, labelField] of fkDefs) {
    db.prepare(
      `INSERT INTO foreign_keys (local_table_id, local_table_field, foreign_table_id, foreign_table_value_field, foreign_table_label_field)
       VALUES (?, ?, ?, ?, ?)`
    ).run(tableIds[local], localField, tableIds[foreign], valueField, labelField);
  }
  console.log(`  Wired ${fkDefs.length} foreign key relationships`);

  db.close();
}

// Branding + plugin registration — unlike the one-time block above, this
// must run every time (not just on first config-db creation), so settings
// and plugins added after the initial /web setup still apply to existing
// installs. There's no admin UI for editing mystery_settings in mystery6, so
// unconditionally overwriting is safe — nothing else can have changed these.
{
  const db = new Database(configDest);

  // See mystery6's AGENTS.md "Branding" section: these three settings drive
  // the nav bar, browser tab title, and login screen.
  db.prepare(`INSERT OR REPLACE INTO mystery_settings (setting_key, setting_value) VALUES ('app_name', 'Best Foot Forward')`).run();
  db.prepare(`INSERT OR REPLACE INTO mystery_settings (setting_key, setting_value) VALUES ('subtitle', 'Job Search Database')`).run();
  db.prepare(`INSERT OR REPLACE INTO mystery_settings (setting_key, setting_value) VALUES ('logo_url', '/images/bff-logo.png')`).run();
  console.log('  Set branding: Best Foot Forward');

  db.prepare(
    `INSERT OR IGNORE INTO plugins (plugin_key, plugin_label, plugin_route, is_active)
     VALUES ('bff-reports', 'BFF Reports', '/api/plugins/bff-reports', 1)`
  ).run();
  console.log('  Registered plugin: bff-reports');

  db.prepare(
    `INSERT OR IGNORE INTO plugins (plugin_key, plugin_label, plugin_route, is_active)
     VALUES ('bff-chat', 'BFF Chat', '/api/plugins/bff-chat', 1)`
  ).run();
  console.log('  Registered plugin: bff-chat');

  db.prepare(
    `INSERT OR IGNORE INTO plugins (plugin_key, plugin_label, plugin_route, is_active)
     VALUES ('bff-graph', 'BFF Graph', '/api/plugins/bff-graph', 1)`
  ).run();
  console.log('  Registered plugin: bff-graph');

  // Nav order follows insertion order — mystery6's src/routes/menu.js selects
  // from `plugins` with no ORDER BY, so rowid decides. Keep bff-about last in
  // this block, and add any new plugin above it.
  db.prepare(
    `INSERT OR IGNORE INTO plugins (plugin_key, plugin_label, plugin_route, is_active)
     VALUES ('bff-about', 'BFF About', '/api/plugins/bff-about', 1)`
  ).run();
  console.log('  Registered plugin: bff-about');

  db.close();
}

// The clone's public/images/ is wiped and recreated on every fresh clone, so
// (unlike the one-time branding row above) the logo file itself must be
// copied in unconditionally on every setup run.
copyFileSync(resolve(BFF_ROOT, 'branding', 'logo-icon.png'), resolve(cloneRoot, 'public', 'images', 'bff-logo.png'));
console.log('  Copied BFF logo into clone');

// .env is written fresh every run — it lives inside the disposable clone
// (mystery6's config.js loads .env from a path relative to its own
// __dirname, non-overridable, so it must land in the clone's own root) and
// is lost whenever the clone is recreated.
const configJsPath = resolve(cloneRoot, 'src', 'config.js');
const noAuthSupported = existsSync(configJsPath) && readFileSync(configJsPath, 'utf8').includes('noAuth');

writeFileSync(envDest, [
  '# Auto-generated by web/mystery/setup.mjs (owned by BestFootForward) — do not edit by hand',
  `TARGET_DB=sqlite://${bffDbPath}`,
  `CONFIG_DB_PATH=${configDest}`,
  `SESSION_SECRET=${randomBytes(32).toString('hex')}`,
  `PORT=${port}`,
  'HTTPS=false',
  'NODE_ENV=development',
  ...(noAuthSupported ? ['NO_AUTH=true', 'NO_AUTH_USER=bff'] : []),
  '',
].join('\n'));
console.log(`  Wrote ${envDest}${noAuthSupported ? ' (NO_AUTH enabled)' : ''}`);

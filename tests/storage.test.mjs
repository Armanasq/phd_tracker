import test from "node:test";
import assert from "node:assert/strict";
import {storageKey,legacyKeyForMigration} from "../site/modules/storage.mjs";

const here={host:"example.github.io",hostname:"example.github.io",pathname:"/my-tracker/"};

test("forks and separate Pages paths do not collide in local state",()=>{
 assert.notEqual(storageKey("phd-atlas-drafts-v1",here),storageKey("phd-atlas-drafts-v1",{...here,pathname:"/other-tracker/"}));
 assert.notEqual(storageKey("phd-atlas-drafts-v1",here),storageKey("phd-atlas-drafts-v1",{...here,host:"other.github.io"}));
 assert.notEqual(storageKey("phd-atlas-drafts-v1",here),storageKey("phd-atlas-prefs-v1",here));
 assert.equal(storageKey("phd-atlas-drafts-v1",{...here,pathname:"/my-tracker/index.html"}),storageKey("phd-atlas-drafts-v1",here));
 assert.equal(storageKey("phd-atlas-drafts-v1",{...here,pathname:"/my-tracker/#dashboard"}),storageKey("phd-atlas-drafts-v1",here));
});
test("legacy migrations are restricted to the original deployment path",()=>{
 assert.equal(legacyKeyForMigration("phd-atlas-drafts-v1",{hostname:"armanasq.github.io",pathname:"/phd_tracker/"}),"phd-atlas-drafts-v1");
 assert.equal(legacyKeyForMigration("phd-atlas-drafts-v1",{hostname:"armanasq.github.io",pathname:"/phd_tracker/index.html"}),"phd-atlas-drafts-v1");
 assert.equal(legacyKeyForMigration("phd-atlas-drafts-v1",here),null);
 assert.equal(legacyKeyForMigration("phd-atlas-drafts-v1",{hostname:"armanasq.github.io",pathname:"/other-tracker/"}),null);
});
test("invalid keys and invalid scope are rejected rather than silently shared",()=>{
 assert.throws(()=>storageKey("../drafts",here),TypeError);
 assert.throws(()=>storageKey("drafts",{host:"",pathname:"/"}),TypeError);
 assert.throws(()=>storageKey("drafts",{host:"valid.github.io",pathname:"invalid"}),TypeError);
});

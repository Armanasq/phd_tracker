export function storageKey(name, context=globalThis.location) {
 if(typeof name!=="string"||!/^[a-z0-9][a-z0-9-]{0,79}$/.test(name))throw new TypeError("Invalid storage key");
 if(!context||typeof context.host!=="string"||!context.host||typeof context.pathname!=="string"||!context.pathname.startsWith("/"))throw new TypeError("Storage origin and path are required");
 const path=context.pathname;
 const directory=path.endsWith("/")?path:path.slice(0,path.lastIndexOf("/")+1);
 return "phd-atlas:instance:"+encodeURIComponent(context.host.toLowerCase())+":"+encodeURIComponent(directory)+":"+name;
}

export function legacyKeyForMigration(name,context=globalThis.location) {
 if(context?.hostname?.toLowerCase()!=="armanasq.github.io")return null;
 if(!["/phd_tracker/","/phd_tracker/index.html"].includes(context.pathname))return null;
 return name;
}

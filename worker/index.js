// Cloudflare Worker using MongoDB Atlas Data API for storage.
// Required configuration (set as secrets/vars in Wrangler or Pages):
// - MONGODB_DATA_API_URL: base URL, e.g. https://data.mongodb-api.com/app/<app-id>/endpoint/data/v1
// - MONGODB_DATA_API_KEY: the Data API key (store as secret)
// - MONGODB_DATA_SOURCE: the Data Source name (cluster), e.g. Cluster0
// - MONGODB_DATABASE: database name
// - MONGODB_COLLECTION: collection name

addEventListener('fetch', event => {
  event.respondWith(handle(event.request));
});

function jsonResponse(obj, status=200){
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type':'application/json;charset=utf-8',
      'Access-Control-Allow-Origin':'*'
    }
  });
}

function getConfig(){
  const url = globalThis.MONGODB_DATA_API_URL || '';
  const key = globalThis.MONGODB_DATA_API_KEY || '';
  const dataSource = globalThis.MONGODB_DATA_SOURCE || '';
  const database = globalThis.MONGODB_DATABASE || '';
  const collection = globalThis.MONGODB_COLLECTION || '';
  return {url,key,dataSource,database,collection};
}

async function callDataAPI(action, body){
  const cfg = getConfig();
  if(!cfg.url || !cfg.key) throw new Error('Missing MongoDB Data API configuration');
  const endpoint = `${cfg.url}/action/${action}`;
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type':'application/json',
      'api-key': cfg.key
    },
    body: JSON.stringify(body)
  });
  const json = await resp.json().catch(()=>null);
  if(!resp.ok) throw new Error((json && json.error) ? json.error : `Data API ${action} failed`);
  return json;
}

async function handle(request){
  const url = new URL(request.url);
  try{
    if(request.method === 'POST' && url.pathname === '/api/submit'){
      return await handleSubmit(request);
    }
    if(request.method === 'GET' && url.pathname === '/api/entries'){
      return await handleList(request);
    }
    return new Response('Not found', {status:404});
  }catch(err){
    return jsonResponse({message: err.message || 'Server error'}, 500);
  }
}

function sanitizeContent(content){
  content = content.toString();
  content = content.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '');
  content = content.replace(/on\w+=\"?[^\"\s>]+\"?/gi, '');
  content = content.replace(/javascript:\/\/[\s\S]*/gi, '');
  return content.trim();
}

async function handleSubmit(request){
  const cfg = getConfig();
  if(!cfg.url || !cfg.key || !cfg.dataSource || !cfg.database || !cfg.collection){
    return jsonResponse({message:'Server not configured (MONGODB data API)'} ,500);
  }
  const body = await request.json().catch(()=>null);
  if(!body) return jsonResponse({message:'Invalid JSON'},400);
  let content = sanitizeContent(body.content || '');
  const tags = (body.tags || '').toString().split(',').map(s=>s.trim()).filter(Boolean);
  if(!content) return jsonResponse({message:'Contenido vacío'}, 400);
  if(content.length > 2000) return jsonResponse({message:'Contenido demasiado largo'}, 400);

  const entry = {
    content,
    tags,
    ts: new Date().toISOString()
  };

  const insertBody = {
    dataSource: cfg.dataSource,
    database: cfg.database,
    collection: cfg.collection,
    document: entry
  };

  const result = await callDataAPI('insertOne', insertBody);
  // result may contain "insertedId" with $oid
  const insertedId = result && result.insertedId ? (result.insertedId.$oid || result.insertedId) : null;
  return jsonResponse({message:'ok', id: insertedId});
}

async function handleList(request){
  const cfg = getConfig();
  if(!cfg.url || !cfg.key || !cfg.dataSource || !cfg.database || !cfg.collection){
    return jsonResponse({message:'Server not configured (MONGODB data API)'} ,500);
  }
  const url = new URL(request.url);
  const limit = Math.min(100, parseInt(url.searchParams.get('limit')||'20'));

  const findBody = {
    dataSource: cfg.dataSource,
    database: cfg.database,
    collection: cfg.collection,
    filter: {},
    sort: { ts: -1 },
    limit
  };

  const result = await callDataAPI('find', findBody);
  const docs = Array.isArray(result.documents) ? result.documents : [];
  return jsonResponse({entries: docs});
}

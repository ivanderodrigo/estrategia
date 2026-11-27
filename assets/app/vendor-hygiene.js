/* Browser-side safeguard while a scheduled research rebuild is pending.
 * The source taxonomy lives in config/current/non_vendor_labels.json; this
 * module never edits or suppresses archival/historical provenance views.
 */
(function(root){
  'use strict';
  const FIELDS=['vendor_relations','manufacturer_relations','vendor_partnerships',
    'linecard_remainder','westcon_overlap','competitor_vendor_overlap'];
  const ASSET=/\.(?:svg|png|jpe?g|webp|gif|ico|avif)(?:\?.*)?$/i;
  const ICON=/^(?:(?:icon|logo|image|imagen|banner)[\s_-]+|.+\s+(?:icon|logo))$/i;
  const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase();
  const fallbackLabels=['Marketing','Recursos','NOVEDADES','Redes','MSSP','GSI',
    'VAR','Partner Portal','Partner Enablement','Privacy Policy','Poland',
    'Pan-EMEA','Infinigate Group','RUCKUS Networks Endorsed'];

  function labelsFromPolicy(policy){
    const labels=new Set(fallbackLabels.map(normalize));
    for(const list of Object.values(policy?.categories||{})){
      if(Array.isArray(list))for(const value of list){
        if(typeof value==='string'&&value.trim())labels.add(normalize(value));
      }
    }
    return labels;
  }
  async function loadPolicy(fetchFn){
    try{
      const result=await fetchFn('config/current/non_vendor_labels.json',{cache:'no-store'});
      if(!result.ok)throw Error('non-vendor policy unavailable');
      return labelsFromPolicy(await result.json());
    }catch(_error){return labelsFromPolicy({});}
  }
  function nonVendor(value,labels){
    return typeof value==='string'&&(
      ASSET.test(value.trim())||ICON.test(value.trim())||labels.has(normalize(value))
    );
  }
  function quarantinePublicRows(rows,labels){
    let removed=0;
    for(const row of rows||[]){
      if(!row||typeof row!=='object')continue;
      for(const fieldId of FIELDS){
        const field=row.fields?.[fieldId];
        if(!field||!Array.isArray(field.value))continue;
        const before=field.value.length;
        field.value=field.value.filter(value=>!nonVendor(value,labels));
        if(field.value.length===before)continue;
        removed+=before-field.value.length;
        if(Array.isArray(field.items))field.items=field.items.filter(item=>!nonVendor(item?.value,labels));
        if(Array.isArray(field.evidence))field.evidence=field.evidence.filter(ev=>!nonVendor(ev?.item_value,labels));
        if(Array.isArray(row.evidence))row.evidence=row.evidence.filter(ev=>
          !((ev?.field===fieldId)&&nonVendor(ev?.item_value,labels)));
        if(!field.value.length){
          field.evidence=[];
          field.confidence=Math.min(Number(field.confidence)||0,0.38);
          field.fact_confidence=Math.min(Number(field.fact_confidence)||0,0.38);
          field.confidence_band='low';
          field.evidence_color='red';
          if(field.assertion_status==='CONFIRMADO')field.assertion_status='PENDIENTE_DE_CONTRASTAR_AFIRMACION';
        }
      }
    }
    return removed;
  }
  const api={labelsFromPolicy,loadPolicy,nonVendor,quarantinePublicRows};
  root.WestconVendorHygiene=api;
  if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);

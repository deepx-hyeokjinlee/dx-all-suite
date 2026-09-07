// (Planner TCO engine moved to dx_planner/ standalone server)

async function init(){
  await loadModels();
  // loadModels() 는 카탈로그를 기다린다. 그 사이에 사용자가 (또는 튜토리얼이,
  // 딥링크가) 다른 화면으로 갔다면 여기서 되돌리면 안 된다 — 부팅이 끝나는
  // 순간 보고 있던 화면이 뒤바뀐다. 아직 초기 화면 그대로일 때만 넘긴다.
  var _active = document.querySelector('.page.active');
  if (!_active || _active.id === 'page-models') nav('models');
  initRunPage();
  initBenchPage();
  initABImages();
  initPipeImages();
  // Pre-load chat models in background so picker is ready when chat opens
  if(typeof _loadChatModels === 'function') setTimeout(_loadChatModels, 500);
  var ipd=$('modal-imgpreview');
  ipd.addEventListener('click',function(){ipd.close()});
  ipd.addEventListener('cancel',function(e){e.preventDefault();ipd.close()});
  $('m-search').addEventListener('input',function(){filterModels()});
}

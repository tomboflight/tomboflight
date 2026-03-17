(function () {
  'use strict';

  const host = window.location.hostname;
  const isLocal =
    host === '127.0.0.1' ||
    host === 'localhost' ||
    host === '::1';

  window.TOL_CONFIG = {
    API_BASE_URL: isLocal ? 'http://127.0.0.1:8000' : 'http://127.0.0.1:8000'
  };
})();
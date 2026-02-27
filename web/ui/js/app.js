/**
 * cubiApp - Lógica frontend (modales, vistas, bridge).
 */
(function() {
  'use strict';

  // ── Sistema de modales ─────────────────────────────────────────────
  function createModal(id, title, content) {
    var existing = document.getElementById(id);
    if (existing) return existing;

    var overlay = document.createElement('div');
    overlay.id = id;
    overlay.className = 'modal-overlay';
    overlay.innerHTML = [
      '<div class="modal-dialog">',
      '  <div class="modal-content">',
      '    <div class="modal-header">',
      '      <h5 class="modal-title">' + (title || '') + '</h5>',
      '      <button type="button" class="close modal-close" aria-label="Cerrar">&times;</button>',
      '    </div>',
      '    <div class="modal-body">' + (content || '') + '</div>',
      '  </div>',
      '</div>'
    ].join('');

    overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;align-items:center;justify-content:center';
    overlay.querySelector('.modal-dialog').style.cssText = 'background:#fff;border-radius:8px;max-width:600px;width:90%;max-height:90vh;overflow:auto;box-shadow:0 4px 20px rgba(0,0,0,0.2)';
    overlay.querySelector('.modal-header').style.cssText = 'padding:16px 20px;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center';
    overlay.querySelector('.modal-title').style.cssText = 'margin:0;font-size:1.25rem';
    overlay.querySelector('.modal-close').style.cssText = 'background:none;border:none;font-size:28px;cursor:pointer;line-height:1;color:#666';
    overlay.querySelector('.modal-body').style.cssText = 'padding:20px';

    document.body.appendChild(overlay);

    overlay.querySelector('.modal-close').onclick = function() { hideModal(id); };
    overlay.onclick = function(e) { if (e.target === overlay) hideModal(id); };

    return overlay;
  }

  function showModal(id) {
    var el = document.getElementById(id);
    if (el) {
      el.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  function hideModal(id) {
    var el = document.getElementById(id);
    if (el) {
      el.style.display = 'none';
      document.body.style.overflow = '';
    }
  }

  // ── Modal Rutas por defecto ─────────────────────────────────────────
  var PATH_SAVE = 'ruta_guardar_presupuestos';
  var PATH_OPEN = 'ruta_abrir_presupuestos';
  var PATH_RELATION = 'ruta_relacion_presupuestos';
  // Coinciden con Settings.PATH_* en Python

  function getDefaultPathsModalContent() {
    return [
      '<p class="text-muted mb-4">Configura las carpetas y archivos por defecto.</p>',
      '<div class="form-group">',
      '  <label>Carpeta para guardar presupuestos nuevos</label>',
      '  <div class="input-group">',
      '    <input type="text" class="form-control" id="path-save" readonly>',
      '    <div class="input-group-append"><button type="button" class="btn btn-secondary btn-browse-dir" data-target="path-save">Examinar</button></div>',
      '    <div class="input-group-append"><button type="button" class="btn btn-outline-secondary btn-clear-path" data-target="path-save">Limpiar</button></div>',
      '  </div>',
      '</div>',
      '<div class="form-group">',
      '  <label>Carpeta para abrir presupuestos existentes</label>',
      '  <div class="input-group">',
      '    <input type="text" class="form-control" id="path-open" readonly>',
      '    <div class="input-group-append"><button type="button" class="btn btn-secondary btn-browse-dir" data-target="path-open">Examinar</button></div>',
      '    <div class="input-group-append"><button type="button" class="btn btn-outline-secondary btn-clear-path" data-target="path-open">Limpiar</button></div>',
      '  </div>',
      '</div>',
      '<div class="form-group">',
      '  <label>Archivo Excel de relación de presupuestos</label>',
      '  <div class="input-group">',
      '    <input type="text" class="form-control" id="path-relation" readonly>',
      '    <div class="input-group-append"><button type="button" class="btn btn-secondary btn-browse-file" data-target="path-relation">Examinar</button></div>',
      '    <div class="input-group-append"><button type="button" class="btn btn-outline-secondary btn-clear-path" data-target="path-relation">Limpiar</button></div>',
      '  </div>',
      '</div>',
      '<div class="modal-footer mt-4 pt-3 border-top">',
      '  <button type="button" class="btn btn-secondary modal-cancel">Cancelar</button>',
      '  <button type="button" class="btn btn-primary btn-save-paths">Guardar</button>',
      '</div>'
    ].join('');
  }

  function showDefaultPathsModal() {
    if (!window.app) {
      console.error('Bridge no disponible');
      return;
    }
    var id = 'modal-default-paths';
    createModal(id, 'Rutas por defecto', getDefaultPathsModalContent());

    var modal = document.getElementById(id);
    var pathSave = modal.querySelector('#path-save');
    var pathOpen = modal.querySelector('#path-open');
    var pathRelation = modal.querySelector('#path-relation');

    window.app.getDefaultPaths(function(jsonStr) {
      var data = JSON.parse(jsonStr);
      pathSave.value = data[PATH_SAVE] || '';
      pathOpen.value = data[PATH_OPEN] || '';
      pathRelation.value = data[PATH_RELATION] || '';
    });

    modal.querySelector('.modal-cancel').onclick = function() { hideModal(id); };

    modal.querySelector('.btn-save-paths').onclick = function() {
      var payload = {};
      payload[PATH_SAVE] = pathSave.value.trim();
      payload[PATH_OPEN] = pathOpen.value.trim();
      payload[PATH_RELATION] = pathRelation.value.trim();

      window.app.saveDefaultPaths(JSON.stringify(payload), function(resultStr) {
        var result = JSON.parse(resultStr);
        if (result.ok) {
          hideModal(id);
          showToast('Rutas guardadas correctamente', 'success');
        } else {
          showToast(result.error || 'Error al guardar', 'danger');
        }
      });
    };

    modal.querySelectorAll('.btn-browse-dir').forEach(function(btn) {
      btn.onclick = function() {
        var target = modal.querySelector('#' + btn.getAttribute('data-target'));
        var current = target.value || '';
        window.app.selectDirectory(current, function(path) {
          if (path) target.value = path;
        });
      };
    });

    modal.querySelectorAll('.btn-browse-file').forEach(function(btn) {
      btn.onclick = function() {
        var target = modal.querySelector('#' + btn.getAttribute('data-target'));
        var current = target.value ? target.value.replace(/[^/\\]*$/, '') : '';
        window.app.selectFile(current, '*.xlsx', function(path) {
          if (path) target.value = path;
        });
      };
    });

    modal.querySelectorAll('.btn-clear-path').forEach(function(btn) {
      btn.onclick = function() {
        var target = modal.querySelector('#' + btn.getAttribute('data-target'));
        target.value = '';
      };
    });

    showModal(id);
  }

  // ── Modal Acerca de ────────────────────────────────────────────────
  function showAboutModal() {
    var id = 'modal-about';
    var content = '<p class="mb-0">cubiApp</p><p class="text-muted mt-2">Gestión de presupuestos.</p><p class="text-muted small">Versión con UI web (Qt WebEngine).</p><div class="modal-footer mt-4 pt-3 border-top"><button type="button" class="btn btn-primary modal-close-btn">Cerrar</button></div>';
    createModal(id, 'Acerca de', content);
    var modal = document.getElementById(id);
    modal.querySelector('.modal-close-btn').onclick = function() { hideModal(id); };
    showModal(id);
  }

  // ── Modal API Key ───────────────────────────────────────────────────
  function showApiKeyModal() {
    if (!window.app) return;
    var id = 'modal-api-key';
    var content = [
      '<p class="text-muted mb-3">Introduce tu API key de Google Gemini. Puedes obtenerla gratis en <a href="https://aistudio.google.com/apikey" target="_blank">aistudio.google.com/apikey</a></p>',
      '<div class="form-group">',
      '  <label>API Key</label>',
      '  <input type="password" class="form-control" id="api-key-input" placeholder="AIza...">',
      '</div>',
      '<div class="modal-footer mt-4 pt-3 border-top">',
      '  <button type="button" class="btn btn-secondary modal-cancel-api">Cancelar</button>',
      '  <button type="button" class="btn btn-primary btn-save-api">Guardar</button>',
      '</div>'
    ].join('');
    createModal(id, 'Configuración IA - API Key', content);

    var modal = document.getElementById(id);
    var input = modal.querySelector('#api-key-input');

    window.app.getApiKey(function(key) {
      input.value = key || '';
    });

    modal.querySelector('.modal-cancel-api').onclick = function() { hideModal(id); };
    modal.querySelector('.btn-save-api').onclick = function() {
      var key = input.value.trim();
      window.app.saveApiKey(key, function(resultStr) {
        var result = JSON.parse(resultStr);
        if (result.ok) {
          hideModal(id);
          showToast('API key guardada correctamente', 'success');
        } else {
          showToast(result.error || 'Error', 'danger');
        }
      });
    };

    showModal(id);
  }

  // ── Toast simple ───────────────────────────────────────────────────
  function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'alert alert-' + (type === 'success' ? 'success' : type === 'danger' ? 'danger' : 'info');
    toast.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:10000;min-width:200px';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
  }

  // ── Vista Configuración (dashboard) ─────────────────────────────────
  var _configInitialized = false;

  function initConfigView() {
    if (!window.app) return;
    var pathSave = document.getElementById('config-path-save');
    var pathOpen = document.getElementById('config-path-open');
    var pathRelation = document.getElementById('config-path-relation');
    var apiKeyInput = document.getElementById('config-api-key');
    if (!pathSave || !pathOpen || !pathRelation || !apiKeyInput) return;

    window.app.getDefaultPaths(function(jsonStr) {
      var data = JSON.parse(jsonStr);
      pathSave.value = data[PATH_SAVE] || '';
      pathOpen.value = data[PATH_OPEN] || '';
      pathRelation.value = data[PATH_RELATION] || '';
    });
    window.app.getApiKey(function(key) {
      apiKeyInput.value = key || '';
    });

    if (_configInitialized) return;
    _configInitialized = true;

    document.getElementById('view-config').querySelector('.btn-save-paths').onclick = function() {
      var payload = {};
      payload[PATH_SAVE] = pathSave.value.trim();
      payload[PATH_OPEN] = pathOpen.value.trim();
      payload[PATH_RELATION] = pathRelation.value.trim();
      window.app.saveDefaultPaths(JSON.stringify(payload), function(resultStr) {
        var result = JSON.parse(resultStr);
        if (result.ok) showToast('Rutas guardadas correctamente', 'success');
        else showToast(result.error || 'Error al guardar', 'danger');
      });
    };

    document.getElementById('view-config').querySelector('.btn-save-api').onclick = function() {
      var key = apiKeyInput.value.trim();
      window.app.saveApiKey(key, function(resultStr) {
        var result = JSON.parse(resultStr);
        if (result.ok) showToast('API key guardada correctamente', 'success');
        else showToast(result.error || 'Error', 'danger');
      });
    };

    document.getElementById('view-config').querySelectorAll('.btn-browse-dir').forEach(function(btn) {
      btn.onclick = function() {
        var targetId = btn.getAttribute('data-target');
        var target = document.getElementById(targetId);
        var current = target ? target.value || '' : '';
        window.app.selectDirectory(current, function(path) {
          if (path && target) target.value = path;
        });
      };
    });

    document.getElementById('view-config').querySelectorAll('.btn-browse-file').forEach(function(btn) {
      btn.onclick = function() {
        var targetId = btn.getAttribute('data-target');
        var target = document.getElementById(targetId);
        var current = target && target.value ? target.value.replace(/[^/\\]*$/, '') : '';
        window.app.selectFile(current, '*.xlsx', function(path) {
          if (path && target) target.value = path;
        });
      };
    });

    document.getElementById('view-config').querySelectorAll('.btn-clear-path').forEach(function(btn) {
      btn.onclick = function() {
        var target = document.getElementById(btn.getAttribute('data-target'));
        if (target) target.value = '';
      };
    });
  }

  // ── Vista Presupuestos ──────────────────────────────────────────────
  var _presupuestosData = null;

  function formatEuro(val) {
    if (val == null || val === '') return '—';
    var n = parseFloat(val);
    if (isNaN(n)) return '—';
    return n.toLocaleString('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function initPresupuestosView() {
    if (!window.app) return;
    var hint = document.getElementById('presupuestos-hint');
    var tabsEl = document.getElementById('presupuestos-tabs');
    var thead = document.getElementById('presupuestos-thead');
    var tbody = document.getElementById('presupuestos-tbody');
    var tableWrap = document.getElementById('presupuestos-table-wrap');
    var emptyEl = document.getElementById('presupuestos-empty');
    var refreshBtn = document.getElementById('presupuestos-refresh');

    function loadBudgets() {
      hint.textContent = 'Cargando presupuestos…';
      hint.classList.remove('d-none');
      tableWrap.classList.add('d-none');
      emptyEl.classList.add('d-none');
      tabsEl.innerHTML = '';

      window.app.getBudgets(function(jsonStr) {
        var data;
        try { data = JSON.parse(jsonStr); } catch (e) { data = { error: 'Error al parsear datos' }; }
        _presupuestosData = data;

        if (data.error) {
          hint.textContent = data.error;
          hint.classList.remove('d-none');
          return;
        }

        var states = data.states || {};
        var stateNames = Object.keys(states);
        if (stateNames.length === 0) {
          hint.textContent = data.root_path ? 'No hay carpetas de estado en: ' + data.root_path : 'Ruta no configurada';
          return;
        }

        hint.textContent = data.root_path || '';
        hint.classList.add('d-none');

        tabsEl.innerHTML = stateNames.map(function(name, i) {
          var count = (states[name] || []).length;
          var active = i === 0 ? ' active' : '';
          return '<li class="nav-item"><a class="nav-link' + active + '" href="#" data-state="' + name.replace(/"/g, '&quot;') + '">' + name + ' (' + count + ')</a></li>';
        }).join('');

        tabsEl.querySelectorAll('.nav-link').forEach(function(link) {
          link.onclick = function(e) {
            e.preventDefault();
            tabsEl.querySelectorAll('.nav-link').forEach(function(l) { l.classList.remove('active'); });
            link.classList.add('active');
            renderTable(link.getAttribute('data-state'));
          };
        });

        var firstState = stateNames[0];
        renderTable(firstState);
        tableWrap.classList.remove('d-none');
      });
    }

    function renderTable(stateName) {
      var projects = (_presupuestosData && _presupuestosData.states && _presupuestosData.states[stateName]) || [];
      thead.innerHTML = '<th>Nº</th><th>Proyecto</th><th>Cliente</th><th>Administración</th><th>Dirección</th><th>Tipo obra</th><th>Fecha</th><th>Total</th><th></th>';
      tbody.innerHTML = '';

      if (projects.length === 0) {
        emptyEl.classList.remove('d-none');
        emptyEl.textContent = 'No hay presupuestos en ' + stateName + '.';
        return;
      }
      emptyEl.classList.add('d-none');

      projects.forEach(function(p) {
        var tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.innerHTML = [
          '<td>' + (p.numero || '') + '</td>',
          '<td>' + (p.nombre_proyecto || '') + '</td>',
          '<td>' + (p.cliente || '') + '</td>',
          '<td>' + (p.administracion_nombre || '') + '</td>',
          '<td>' + (p.direccion || '') + '</td>',
          '<td>' + (p.tipo_obra || '') + '</td>',
          '<td>' + (p.fecha || '') + '</td>',
          '<td>' + formatEuro(p.total) + '</td>',
          '<td><button type="button" class="btn btn-sm btn-light-primary btn-open-budget" data-ruta="' + (p.ruta_excel || '').replace(/"/g, '&quot;') + '">Abrir</button></td>'
        ].join('');
        tr.onclick = function(ev) {
          if (ev.target.classList.contains('btn-open-budget')) return;
          if (p.ruta_excel) window.app.openBudget(p.ruta_excel, function(r) {
            var res = JSON.parse(r);
            if (!res.ok) showToast(res.error || 'Error', 'danger');
          });
        };
        tr.querySelector('.btn-open-budget').onclick = function(e) {
          e.stopPropagation();
          if (p.ruta_excel) window.app.openBudget(p.ruta_excel, function(r) {
            var res = JSON.parse(r);
            if (!res.ok) showToast(res.error || 'Error', 'danger');
          });
        };
        tbody.appendChild(tr);
      });
    }

    if (refreshBtn) refreshBtn.onclick = loadBudgets;
    loadBudgets();
  }

  // ── Vista Base de datos (DataTables) ─────────────────────────────────
  var _dtAdmin = null;
  var _dtComunidad = null;
  var _basedatosResizeBound = false;

  function initBasedatosView() {
    if (!window.app) return;
    if (typeof jQuery === 'undefined' || !jQuery.fn.DataTable) {
      console.warn('DataTables no disponible');
      return;
    }
    var $ = jQuery;
    var refreshBtn = document.getElementById('basedatos-refresh');
    var tabAdmin = document.getElementById('basedatos-tab-admin');
    var tabComunidad = document.getElementById('basedatos-tab-comunidad');
    var tabs = document.querySelectorAll('#basedatos-tabs .nav-link');

    function esc(v) {
      return String(v == null || v === '' ? '—' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function actionIcon(action) {
      if (action === 'view') {
        return '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">' +
          '<path fill="currentColor" d="M8 3C3.8 3 1.25 7.38 1.15 7.56a.9.9 0 0 0 0 .88C1.25 8.62 3.8 13 8 13s6.75-4.38 6.85-4.56a.9.9 0 0 0 0-.88C14.75 7.38 12.2 3 8 3m0 8.5A3.5 3.5 0 1 1 8 4.5a3.5 3.5 0 0 1 0 7m0-5.5a2 2 0 1 0 0 4a2 2 0 0 0 0-4"/>' +
          '</svg>';
      }
      if (action === 'edit') {
        return '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">' +
          '<path fill="currentColor" d="M12.15 1.8a1.9 1.9 0 0 1 2.69 2.69l-8.8 8.8a1 1 0 0 1-.44.25l-3.02.86a.75.75 0 0 1-.93-.93l.86-3.02a1 1 0 0 1 .25-.44zM11.1 3.9L4 11l-.4 1.4L5 12l7.1-7.1z"/>' +
          '</svg>';
      }
      return '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">' +
        '<path fill="currentColor" d="M5.5 5.5a1 1 0 1 1 0-2a1 1 0 0 1 0 2m2.5 0a1 1 0 1 1 0-2a1 1 0 0 1 0 2m2.5 0a1 1 0 1 1 0-2a1 1 0 0 1 0 2"/>' +
        '<path fill="currentColor" d="M3 2h10l-.8 11.2A2 2 0 0 1 10.2 15H5.8a2 2 0 0 1-1.99-1.8zM6 1h4a1 1 0 0 1 1 1v1H5V2a1 1 0 0 1 1-1"/>' +
        '</svg>';
    }

    function iconButton(action, cls, title) {
      return '<button type="button" class="btn btn-icon btn-xs ' + cls + '" title="' + esc(title) + '" aria-label="' + esc(title) + '">' +
        actionIcon(action) + '</button>';
    }

    function showReadonlyModal(id, title, fields, onEdit) {
      var rows = fields.map(function(f) {
        return '<div class="basedatos-detail-item">' +
          '<div class="basedatos-detail-label">' + esc(f.label) + '</div>' +
          '<div class="basedatos-detail-value">' + esc(f.value) + '</div>' +
          '</div>';
      }).join('');
      var content = '<div class="basedatos-detail-grid">' + rows + '</div>' +
        '<div class="modal-footer mt-4 pt-3 border-top">' +
        (onEdit ? '<button type="button" class="btn btn-light-primary modal-edit-readonly mr-2">' + actionIcon('edit') + '<span class="ml-2">Editar</span></button>' : '') +
        '<button type="button" class="btn btn-primary modal-close-readonly">Cerrar</button>' +
        '</div>';
      createModal(id, title, content);
      var modal = document.getElementById(id);
      var dialog = modal.querySelector('.modal-dialog');
      if (dialog) {
        dialog.style.maxWidth = '760px';
        dialog.style.width = '94%';
        dialog.style.overflowX = 'hidden';
      }
      modal.querySelector('.modal-close-readonly').onclick = function() { hideModal(id); };
      if (onEdit && modal.querySelector('.modal-edit-readonly')) {
        modal.querySelector('.modal-edit-readonly').onclick = function() {
          hideModal(id);
          onEdit();
        };
      }
      showModal(id);
    }

    function showAdminDetails(rowData) {
      showReadonlyModal('modal-admin-view', 'Detalle administración', [
        { label: 'Nombre', value: rowData.nombre },
        { label: 'Dirección', value: rowData.direccion },
        { label: 'Email', value: rowData.email },
        { label: 'Teléfono', value: rowData.telefono },
        { label: 'Contactos', value: rowData.contactos }
      ], function() {
        showAdminModal(rowData.id);
      });
    }

    function showComunidadDetails(rowData) {
      showReadonlyModal('modal-comunidad-view', 'Detalle comunidad', [
        { label: 'Nombre', value: rowData.nombre },
        { label: 'CIF', value: rowData.cif },
        { label: 'Dirección', value: rowData.direccion },
        { label: 'Email', value: rowData.email },
        { label: 'Teléfono', value: rowData.telefono },
        { label: 'Administración', value: rowData.nombre_administracion },
        { label: 'Contactos', value: rowData.contactos }
      ], function() {
        showComunidadModal(rowData.id);
      });
    }

    function initAdminTable(data) {
      var tbl = $('#kt_datatable_admin');
      if (_dtAdmin) { _dtAdmin.destroy(); tbl.find('tbody').empty(); }
      _dtAdmin = tbl.DataTable({
        data: data || [],
        paging: false,
        scrollY: '52vh',
        scrollCollapse: true,
        scrollX: true,
        autoWidth: false,
        responsive: true,
        language: {
          search: 'Buscar:', info: '_START_ - _END_ de _TOTAL_',
          emptyTable: 'Sin datos', zeroRecords: 'Sin resultados'
        },
        columns: [
          { data: 'nombre', defaultContent: '—' },
          { data: 'direccion', defaultContent: '—' },
          { data: 'email', defaultContent: '—' },
          { data: 'telefono', defaultContent: '—' },
          { data: 'contactos', defaultContent: '—' },
          {
            data: 'id',
            orderable: false,
            searchable: false,
            render: function() {
              return '<div class="d-flex align-items-center">' +
                iconButton('view', 'btn-light-info btn-view-admin mr-1', 'Ver detalle') +
                iconButton('edit', 'btn-light-primary btn-edit-admin mr-1', 'Editar') +
                iconButton('delete', 'btn-light-danger btn-delete-admin', 'Eliminar') +
                '</div>';
            }
          }
        ],
        order: [[0, 'asc']],
        createdRow: function(row) {
          $(row).find('td').addClass('py-2');
        },
        columnDefs: [
          { targets: '_all', className: 'align-middle' },
          { targets: [1, 2, 4], className: 'text-wrap' },
          { targets: -1, width: '112px' }
        ]
      });
      tbl.off('click').on('click', '.btn-edit-admin', function() {
        var row = _dtAdmin.row($(this).closest('tr'));
        if (row.data()) showAdminModal(row.data().id);
      });
      tbl.on('click', '.btn-view-admin', function() {
        var row = _dtAdmin.row($(this).closest('tr'));
        if (row.data()) showAdminDetails(row.data());
      });
      tbl.on('click', '.btn-delete-admin', function() {
        var row = _dtAdmin.row($(this).closest('tr'));
        if (row.data()) deleteAdmin(row.data().id);
      });
    }

    function initComunidadTable(data) {
      var tbl = $('#kt_datatable_comunidad');
      if (_dtComunidad) { _dtComunidad.destroy(); tbl.find('tbody').empty(); }
      _dtComunidad = tbl.DataTable({
        data: data || [],
        paging: false,
        scrollY: '52vh',
        scrollCollapse: true,
        scrollX: true,
        autoWidth: false,
        responsive: true,
        language: {
          search: 'Buscar:', info: '_START_ - _END_ de _TOTAL_',
          emptyTable: 'Sin datos', zeroRecords: 'Sin resultados'
        },
        columns: [
          { data: 'nombre', defaultContent: '—' },
          { data: 'cif', defaultContent: '—' },
          { data: 'direccion', defaultContent: '—' },
          { data: 'email', defaultContent: '—' },
          { data: 'telefono', defaultContent: '—' },
          { data: 'nombre_administracion', defaultContent: '—' },
          { data: 'contactos', defaultContent: '—' },
          {
            data: 'id',
            orderable: false,
            searchable: false,
            render: function() {
              return '<div class="d-flex align-items-center">' +
                iconButton('view', 'btn-light-info btn-view-comunidad mr-1', 'Ver detalle') +
                iconButton('edit', 'btn-light-primary btn-edit-comunidad mr-1', 'Editar') +
                iconButton('delete', 'btn-light-danger btn-delete-comunidad', 'Eliminar') +
                '</div>';
            }
          }
        ],
        order: [[0, 'asc']],
        createdRow: function(row) {
          $(row).find('td').addClass('py-2');
        },
        columnDefs: [
          { targets: '_all', className: 'align-middle' },
          { targets: [2, 3, 6], className: 'text-wrap' },
          { targets: -1, width: '112px' }
        ]
      });
      tbl.off('click').on('click', '.btn-edit-comunidad', function() {
        var row = _dtComunidad.row($(this).closest('tr'));
        if (row.data()) showComunidadModal(row.data().id);
      });
      tbl.on('click', '.btn-view-comunidad', function() {
        var row = _dtComunidad.row($(this).closest('tr'));
        if (row.data()) showComunidadDetails(row.data());
      });
      tbl.on('click', '.btn-delete-comunidad', function() {
        var row = _dtComunidad.row($(this).closest('tr'));
        if (row.data()) deleteComunidad(row.data().id);
      });
    }

    function loadData() {
      window.app.getAdministraciones(function(jsonStr) {
        try { initAdminTable(JSON.parse(jsonStr) || []); } catch (e) { initAdminTable([]); }
      });
      window.app.getComunidades(function(jsonStr) {
        try { initComunidadTable(JSON.parse(jsonStr) || []); } catch (e) { initComunidadTable([]); }
      });
    }

    function showAdminModal(editId) {
      var title = editId ? 'Editar administración' : 'Añadir administración';
      var content = [
        '<div class="form-group"><label>Nombre *</label><input type="text" class="form-control" id="admin-form-nombre" required></div>',
        '<div class="form-group"><label>Email</label><input type="email" class="form-control" id="admin-form-email"></div>',
        '<div class="form-group"><label>Teléfono</label><input type="text" class="form-control" id="admin-form-telefono"></div>',
        '<div class="form-group"><label>Dirección</label><input type="text" class="form-control" id="admin-form-direccion"></div>',
        '<div class="modal-footer mt-4 pt-3 border-top">',
        '  <button type="button" class="btn btn-secondary modal-cancel-admin">Cancelar</button>',
        '  <button type="button" class="btn btn-primary btn-save-admin">Guardar</button>',
        '</div>'
      ].join('');
      createModal('modal-admin-form', title, content);
      var modal = document.getElementById('modal-admin-form');
      var nombre = modal.querySelector('#admin-form-nombre');
      var email = modal.querySelector('#admin-form-email');
      var telefono = modal.querySelector('#admin-form-telefono');
      var direccion = modal.querySelector('#admin-form-direccion');

      modal.querySelector('.modal-cancel-admin').onclick = function() { hideModal('modal-admin-form'); };
      modal.querySelector('.btn-save-admin').onclick = function() {
        var payload = { nombre: nombre.value.trim(), email: email.value.trim(), telefono: telefono.value.trim(), direccion: direccion.value.trim() };
        if (!payload.nombre) { showToast('El nombre es obligatorio', 'danger'); return; }
        if (editId) {
          payload.id = editId;
          window.app.updateAdministracion(JSON.stringify(payload), function(resultStr) {
            var res = JSON.parse(resultStr);
            if (res.ok) { hideModal('modal-admin-form'); loadData(); showToast('Guardado correctamente', 'success'); }
            else showToast(res.error || 'Error', 'danger');
          });
        } else {
          window.app.createAdministracion(JSON.stringify(payload), function(resultStr) {
            var res = JSON.parse(resultStr);
            if (res.ok) { hideModal('modal-admin-form'); loadData(); showToast('Administración creada', 'success'); }
            else showToast(res.error || 'Error', 'danger');
          });
        }
      };

      if (editId) {
        window.app.getAdministracion(editId, function(jsonStr) {
          var r = JSON.parse(jsonStr);
          if (r && r.id) {
            nombre.value = r.nombre || '';
            email.value = r.email || '';
            telefono.value = r.telefono || '';
            direccion.value = r.direccion || '';
          }
        });
      } else {
        nombre.value = '';
        email.value = '';
        telefono.value = '';
        direccion.value = '';
      }
      showModal('modal-admin-form');
    }

    function showComunidadModal(editId) {
      var title = editId ? 'Editar comunidad' : 'Añadir comunidad';
      var content = [
        '<div class="form-group"><label>Nombre *</label><input type="text" class="form-control" id="com-form-nombre" required></div>',
        '<div class="form-group"><label>Administración *</label><select class="form-control" id="com-form-admin"></select></div>',
        '<div class="form-group"><label>CIF</label><input type="text" class="form-control" id="com-form-cif"></div>',
        '<div class="form-group"><label>Dirección</label><input type="text" class="form-control" id="com-form-direccion"></div>',
        '<div class="form-group"><label>Email</label><input type="email" class="form-control" id="com-form-email"></div>',
        '<div class="form-group"><label>Teléfono</label><input type="text" class="form-control" id="com-form-telefono"></div>',
        '<div class="modal-footer mt-4 pt-3 border-top">',
        '  <button type="button" class="btn btn-secondary modal-cancel-com">Cancelar</button>',
        '  <button type="button" class="btn btn-primary btn-save-com">Guardar</button>',
        '</div>'
      ].join('');
      createModal('modal-com-form', title, content);
      var modal = document.getElementById('modal-com-form');
      var select = modal.querySelector('#com-form-admin');

      function populateForm(r) {
        if (!r || !r.id) return;
        modal.querySelector('#com-form-nombre').value = r.nombre || '';
        modal.querySelector('#com-form-cif').value = r.cif || '';
        modal.querySelector('#com-form-direccion').value = r.direccion || '';
        modal.querySelector('#com-form-email').value = r.email || '';
        modal.querySelector('#com-form-telefono').value = r.telefono || '';
        select.value = r.administracion_id || '';
      }

      window.app.getAdministracionesList(function(jsonStr) {
        var admins = JSON.parse(jsonStr) || [];
        select.innerHTML = '<option value="">— Selecciona administración —</option>' + admins.map(function(a) {
          return '<option value="' + a.id + '">' + (a.nombre || '') + '</option>';
        }).join('');
        if (editId) {
          window.app.getComunidad(editId, function(cJson) {
            var r = JSON.parse(cJson);
            populateForm(r);
          });
        }
      });

      modal.querySelector('.modal-cancel-com').onclick = function() { hideModal('modal-com-form'); };
      modal.querySelector('.btn-save-com').onclick = function() {
        var payload = {
          nombre: modal.querySelector('#com-form-nombre').value.trim(),
          administracion_id: parseInt(select.value, 10) || 0,
          cif: modal.querySelector('#com-form-cif').value.trim(),
          direccion: modal.querySelector('#com-form-direccion').value.trim(),
          email: modal.querySelector('#com-form-email').value.trim(),
          telefono: modal.querySelector('#com-form-telefono').value.trim()
        };
        if (!payload.nombre) { showToast('El nombre es obligatorio', 'danger'); return; }
        if (!payload.administracion_id) { showToast('La administración es obligatoria', 'danger'); return; }
        if (editId) {
          payload.id = editId;
          window.app.updateComunidad(JSON.stringify(payload), function(resultStr) {
            var res = JSON.parse(resultStr);
            if (res.ok) { hideModal('modal-com-form'); loadData(); showToast('Guardado correctamente', 'success'); }
            else showToast(res.error || 'Error', 'danger');
          });
        } else {
          window.app.createComunidad(JSON.stringify(payload), function(resultStr) {
            var res = JSON.parse(resultStr);
            if (res.ok) { hideModal('modal-com-form'); loadData(); showToast('Comunidad creada', 'success'); }
            else showToast(res.error || 'Error', 'danger');
          });
        }
      };

      if (!editId) {
        modal.querySelector('#com-form-nombre').value = '';
        modal.querySelector('#com-form-cif').value = '';
        modal.querySelector('#com-form-direccion').value = '';
        modal.querySelector('#com-form-email').value = '';
        modal.querySelector('#com-form-telefono').value = '';
        select.value = '';
      }
      showModal('modal-com-form');
    }

    function deleteAdmin(id) {
      if (!confirm('¿Eliminar esta administración?')) return;
      window.app.deleteAdministracion(id, function(resultStr) {
        var res = JSON.parse(resultStr);
        if (res.ok) { loadData(); showToast('Eliminado', 'success'); }
        else showToast(res.error || 'Error', 'danger');
      });
    }

    function deleteComunidad(id) {
      if (!confirm('¿Eliminar esta comunidad?')) return;
      window.app.deleteComunidad(id, function(resultStr) {
        var res = JSON.parse(resultStr);
        if (res.ok) { loadData(); showToast('Eliminado', 'success'); }
        else showToast(res.error || 'Error', 'danger');
      });
    }

    tabs.forEach(function(t) {
      t.onclick = function(e) {
        e.preventDefault();
        tabs.forEach(function(tab) { tab.classList.remove('active'); });
        t.classList.add('active');
        var tabName = t.getAttribute('data-tab');
        if (tabAdmin) tabAdmin.classList.toggle('d-none', tabName !== 'admin');
        if (tabComunidad) tabComunidad.classList.toggle('d-none', tabName !== 'comunidad');
        setTimeout(function() {
          if (_dtAdmin) _dtAdmin.columns.adjust();
          if (_dtComunidad) _dtComunidad.columns.adjust();
        }, 0);
      };
    });

    if (!_basedatosResizeBound) {
      _basedatosResizeBound = true;
      window.addEventListener('resize', function() {
        if (_dtAdmin) _dtAdmin.columns.adjust();
        if (_dtComunidad) _dtComunidad.columns.adjust();
      });
    }

    if (refreshBtn) refreshBtn.onclick = loadData;
    document.querySelector('.btn-add-admin').onclick = function() { showAdminModal(null); };
    document.querySelector('.btn-add-comunidad').onclick = function() { showComunidadModal(null); };

    loadData();
  }

  // ── Exportar para uso global ───────────────────────────────────────
  window.appModals = {
    showDefaultPaths: showDefaultPathsModal,
    showAbout: showAboutModal,
    showApiKey: showApiKeyModal,
    showToast: showToast,
    initConfigView: initConfigView,
    initPresupuestosView: initPresupuestosView,
    initBasedatosView: initBasedatosView
  };
})();

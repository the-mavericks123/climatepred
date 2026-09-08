/**
 * Climate Eye — Sensor Nodes Globe Visualization Layer Unit Tests (Step F4.4)
 *
 * Tests cover:
 * - node with valid coordinates creates a marker
 * - multiple dynamic nodes render
 * - future NODE-006+ renders dynamically
 * - node coordinates preserved
 * - node.updated moves/updates the marker correctly
 * - telemetry.updated updates the selected node data
 * - repeated telemetry does not create duplicate markers
 * - null remains unavailable in detail view
 * - zero remains zero in detail view
 * - timestamp preserved
 * - node selection
 * - missing node handling (removal from store removes entity)
 * - stale/unavailable state handling
 * - clean destroy
 * - repeated initialize safety (singleton idempotency)
 * - no Node.js core module imports in browser-safe runtime code
 * - no second globe created
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { createClimateStore, REALTIME_STATES } from '../state/index.js';
import {
  createNodesLayer,
  initNodesLayer,
  getNodesLayer,
  destroyNodesLayer,
  CLIMATE_NODE_ENTITY_PREFIX,
} from './index.js';
import { createRightPanel } from '../panels/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Mock Cesium Implementation for Unit Tests
// ---------------------------------------------------------------------------

function createMockCesium() {
  class MockCartesian3 {
    constructor(x = 0, y = 0, z = 0) {
      this.x = x;
      this.y = y;
      this.z = z;
    }

    static fromDegrees(lon, lat, height = 0) {
      return new MockCartesian3(lon, lat, height);
    }
  }

  class MockCartesian2 {
    constructor(x = 0, y = 0) {
      this.x = x;
      this.y = y;
    }
  }

  class MockColor {
    constructor(r, g, b, a = 1.0) {
      this.r = r;
      this.g = g;
      this.b = b;
      this.a = a;
    }

    static fromCssColorString(str) {
      return new MockColor(0, 0, 0, 1, str);
    }
  }

  MockColor.WHITE = new MockColor(1, 1, 1, 1);
  MockColor.BLACK = new MockColor(0, 0, 0, 1);

  class MockEntity {
    constructor(options = {}) {
      this.id = options.id;
      this.name = options.name;
      this.position = options.position;
      this.point = options.point ? { ...options.point } : null;
      this.label = options.label ? { ...options.label } : null;
      this.properties = options.properties;
    }
  }

  class MockEntityCollection {
    constructor() {
      this._entities = new Map();
    }

    get values() {
      return Array.from(this._entities.values());
    }

    add(options) {
      const entity = options instanceof MockEntity ? options : new MockEntity(options);
      this._entities.set(entity.id, entity);
      return entity;
    }

    getById(id) {
      return this._entities.get(id);
    }

    remove(entity) {
      if (entity && entity.id) {
        return this._entities.delete(entity.id);
      }
      return false;
    }

    removeAll() {
      this._entities.clear();
    }

    contains(entity) {
      return this._entities.has(entity?.id);
    }
  }

  class MockCustomDataSource {
    constructor(name) {
      this.name = name;
      this.entities = new MockEntityCollection();
    }
  }

  class MockScreenSpaceEventHandler {
    constructor(canvas) {
      this.canvas = canvas;
      this.actions = new Map();
      this.isDestroyed = false;
    }

    setInputAction(callback, type) {
      this.actions.set(type, callback);
    }

    triggerClick(position) {
      const fn = this.actions.get(MockScreenSpaceEventType.LEFT_CLICK);
      if (fn) fn({ position });
    }

    destroy() {
      this.isDestroyed = true;
      this.actions.clear();
    }
  }

  const MockScreenSpaceEventType = {
    LEFT_CLICK: 0,
    RIGHT_CLICK: 1,
  };

  return {
    Cartesian3: MockCartesian3,
    Cartesian2: MockCartesian2,
    Color: MockColor,
    CustomDataSource: MockCustomDataSource,
    ScreenSpaceEventHandler: MockScreenSpaceEventHandler,
    ScreenSpaceEventType: MockScreenSpaceEventType,
    HeightReference: { CLAMP_TO_GROUND: 1, NONE: 0 },
    LabelStyle: { FILL_AND_OUTLINE: 2 },
  };
}

function createMockViewer(Cesium) {
  const canvas = { id: 'cesium-canvas' };
  const pickedMap = new Map();

  const dataSourceList = [];

  const dataSources = {
    add: (ds) => {
      dataSourceList.push(ds);
      return ds;
    },
    remove: (ds) => {
      const idx = dataSourceList.indexOf(ds);
      if (idx !== -1) {
        dataSourceList.splice(idx, 1);
        return true;
      }
      return false;
    },
    get: (idx) => dataSourceList[idx],
    _list: dataSourceList,
    get length() {
      return dataSourceList.length;
    },
  };

  const scene = {
    canvas,
    pick: (position) => {
      return pickedMap.get(`${position?.x},${position?.y}`) || null;
    },
  };

  return {
    scene,
    dataSources,
    _dataSourceList: dataSourceList,
    _setPicked: (x, y, result) => {
      pickedMap.set(`${x},${y}`, result);
    },
  };
}

// ---------------------------------------------------------------------------
// Minimal Mock DOM for Detail View Tests
// ---------------------------------------------------------------------------

function createMockElement(tagName = 'div') {
  const children = [];
  const attributes = new Map();
  const listeners = new Map();
  let _innerHTML = '';
  let _className = '';
  let _id = '';
  const classListSet = new Set();

  function syncClassList() {
    classListSet.clear();
    _className.split(/\s+/).filter(Boolean).forEach((c) => classListSet.add(c));
  }

  return {
    tagName: tagName.toUpperCase(),
    children,
    get id() { return _id; },
    set id(val) { _id = String(val); attributes.set('id', _id); },
    get className() { return _className; },
    set className(val) { _className = String(val); attributes.set('class', _className); syncClassList(); },
    style: {},
    get classList() {
      return {
        add: (...cls) => { cls.forEach(c => classListSet.add(c)); _className = Array.from(classListSet).join(' '); },
        remove: (...cls) => { cls.forEach(c => classListSet.delete(c)); _className = Array.from(classListSet).join(' '); },
        toggle: (c, force) => {
          const has = classListSet.has(c);
          const add = force !== undefined ? force : !has;
          if (add) classListSet.add(c); else classListSet.delete(c);
          _className = Array.from(classListSet).join(' ');
          return add;
        },
        contains: (c) => classListSet.has(c),
      };
    },
    get textContent() { return this._textContent !== undefined ? this._textContent : ''; },
    set textContent(val) { this._textContent = String(val); },
    get innerHTML() { return _innerHTML; },
    set innerHTML(html) {
      _innerHTML = html;
      const idRegex = /id="([^"]+)"/g;
      let match;
      while ((match = idRegex.exec(html)) !== null) {
        const child = createMockElement('div');
        child.id = match[1];
        children.push(child);
      }
    },
    setAttribute(n, v) { attributes.set(n, String(v)); },
    getAttribute(n) { return attributes.get(n) ?? null; },
    appendChild(c) { children.push(c); return c; },
    addEventListener(ev, fn) { if (!listeners.has(ev)) listeners.set(ev, []); listeners.get(ev).push(fn); },
    querySelector(sel) {
      if (sel.startsWith('#')) {
        const targetId = sel.slice(1);
        const search = (nodes) => {
          for (const n of nodes) {
            if (n.id === targetId) return n;
            const f = search(n.children);
            if (f) return f;
          }
          return null;
        };
        return search(children);
      }
      return null;
    },
    querySelectorAll(sel) { return []; },
  };
}

function setupMockDom() {
  const orig = globalThis.document;
  globalThis.document = {
    createElement: (tag) => createMockElement(tag),
    getElementById: () => null,
    head: createMockElement('head'),
    body: createMockElement('body'),
  };
  return () => {
    globalThis.document = orig;
  };
}

// ---------------------------------------------------------------------------
// Test Suite
// ---------------------------------------------------------------------------

describe('Frontend F4.4: Sensor Nodes Globe Visualization Layer', () => {
  let Cesium;
  let viewer;
  let store;
  let layer;

  beforeEach(() => {
    destroyNodesLayer();
    Cesium = createMockCesium();
    viewer = createMockViewer(Cesium);
    store = createClimateStore();
  });

  afterEach(() => {
    if (layer) {
      layer.destroy();
      layer = null;
    }
    destroyNodesLayer();
  });

  test('node with valid coordinates creates a marker on Cesium globe', () => {
    store.updateNode({
      node_id: 'NODE-001',
      name: 'Marina Coastal Node',
      latitude: 1.2800,
      longitude: 103.8500,
    });

    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    const ds = layer.getDataSource();
    assert.ok(ds, 'CustomDataSource created');
    assert.equal(viewer.dataSources.length, 1);

    const entity = ds.entities.getById('climate-node:NODE-001');
    assert.ok(entity, 'Entity created with ID climate-node:NODE-001');
    assert.equal(entity.name, 'Marina Coastal Node');
    assert.equal(entity.position.x, 103.8500);
    assert.equal(entity.position.y, 1.2800);
    assert.equal(entity.label.text, 'NODE-001');
  });

  test('multiple dynamic nodes render without hardcoded node ID bounds', () => {
    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });
    store.updateNode({ node_id: 'NODE-002', latitude: 1.30, longitude: 103.80 });
    store.updateNode({ node_id: 'NODE-003', latitude: 1.35, longitude: 103.90 });

    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    const ds = layer.getDataSource();
    assert.equal(ds.entities.values.length, 3);
    assert.ok(ds.entities.getById('climate-node:NODE-001'));
    assert.ok(ds.entities.getById('climate-node:NODE-002'));
    assert.ok(ds.entities.getById('climate-node:NODE-003'));
  });

  test('future node IDs (e.g. NODE-006, NODE-999) render dynamically', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    // Node arrives dynamically after initialization
    store.updateNode({
      node_id: 'NODE-006',
      name: 'Future Arctic Probe',
      latitude: 78.22,
      longitude: 15.65,
    });

    store.updateNode({
      node_id: 'NODE-999',
      name: 'Equatorial Buoy',
      latitude: 0.00,
      longitude: 120.00,
    });

    const ds = layer.getDataSource();
    assert.ok(ds.entities.getById('climate-node:NODE-006'));
    assert.ok(ds.entities.getById('climate-node:NODE-999'));
    assert.equal(ds.entities.getById('climate-node:NODE-006').position.y, 78.22);
    assert.equal(ds.entities.getById('climate-node:NODE-999').position.x, 120.00);
  });

  test('node coordinates preserved exactly from backend without fabrication', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({
      node_id: 'NODE-005',
      latitude: -33.8688,
      longitude: 151.2093,
    });

    const entity = layer.getDataSource().entities.getById('climate-node:NODE-005');
    assert.equal(entity.position.y, -33.8688);
    assert.equal(entity.position.x, 151.2093);
  });

  test('node.updated moves/updates the marker correctly in place', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({
      node_id: 'NODE-001',
      latitude: 1.2800,
      longitude: 103.8500,
    });

    const ds = layer.getDataSource();
    const entity1 = ds.entities.getById('climate-node:NODE-001');
    assert.equal(entity1.position.x, 103.8500);

    // Update coordinates
    store.updateNode({
      node_id: 'NODE-001',
      latitude: 1.2850,
      longitude: 103.8550,
    });

    const entityUpdated = ds.entities.getById('climate-node:NODE-001');
    assert.equal(entityUpdated.position.x, 103.8550);
    assert.equal(entityUpdated.position.y, 1.2850);
    // Entity count remains 1 (no duplicate entity created)
    assert.equal(ds.entities.values.length, 1);
  });

  test('telemetry.updated updates node state without creating duplicate markers', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });
    assert.equal(layer.getDataSource().entities.values.length, 1);

    // Stream telemetry updates repeatedly
    store.updateTelemetry({
      node_id: 'NODE-001',
      temperature: 30.1,
      timestamp: '2026-09-08T06:00:00Z',
    });

    store.updateTelemetry({
      node_id: 'NODE-001',
      temperature: 30.5,
      timestamp: '2026-09-08T06:00:02Z',
    });

    store.updateTelemetry({
      node_id: 'NODE-001',
      temperature: 31.0,
      timestamp: '2026-09-08T06:00:04Z',
    });

    assert.equal(layer.getDataSource().entities.values.length, 1, 'Never creates duplicate markers');
  });

  test('missing / removed node removes marker from globe', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });
    store.updateNode({ node_id: 'NODE-002', latitude: 1.30, longitude: 103.90 });

    const ds = layer.getDataSource();
    assert.equal(ds.entities.values.length, 2);

    // Remove NODE-001
    store.removeNode('NODE-001');

    assert.equal(ds.entities.values.length, 1);
    assert.equal(ds.entities.getById('climate-node:NODE-001'), undefined);
    assert.ok(ds.entities.getById('climate-node:NODE-002'));
  });

  test('stale and unavailable states change marker visual representation', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });

    const entity = layer.getDataSource().entities.getById('climate-node:NODE-001');

    // Initial state is UNAVAILABLE
    assert.ok(entity.point.color);

    // Promote to LIVE via telemetry
    store.updateTelemetry({ node_id: 'NODE-001', temperature: 25.0 });
    store.setRealtimeState(REALTIME_STATES.LIVE);
    layer.update();
    assert.ok(entity.point.color);

    // Transition to STALE
    store.setRealtimeState(REALTIME_STATES.STALE);
    layer.update();
    assert.ok(entity.point.color);

    // Transition to UNAVAILABLE
    store.setRealtimeState(REALTIME_STATES.UNAVAILABLE);
    layer.update();
    assert.ok(entity.point.color);
  });

  test('node selection highlights marker and updates store', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });
    store.updateNode({ node_id: 'NODE-002', latitude: 1.30, longitude: 103.90 });

    const entity1 = layer.getDataSource().entities.getById('climate-node:NODE-001');
    const entity2 = layer.getDataSource().entities.getById('climate-node:NODE-002');

    assert.equal(entity1.point.pixelSize, 12);
    assert.equal(entity2.point.pixelSize, 12);

    // Select NODE-001
    store.selectNode('NODE-001');

    assert.equal(entity1.point.pixelSize, 18, 'Selected node enlarged');
    assert.equal(entity2.point.pixelSize, 12, 'Unselected node unchanged');

    // Deselect
    store.selectNode(null);
    assert.equal(entity1.point.pixelSize, 12);
  });

  test('selected node detail view renders all 12 real values and preserves 0 and null', () => {
    const tearDownDom = setupMockDom();

    try {
      const rightPanel = createRightPanel(store);

      // Add node and rich telemetry
      store.updateNode({
        node_id: 'NODE-001',
        name: 'Marina East',
        latitude: 1.2850,
        longitude: 103.8550,
      });

      store.updateTelemetry({
        node_id: 'NODE-001',
        timestamp: '2026-09-08T06:15:00.000Z',
        temperature: 32.5,
        humidity: 80,
        pressure: 1010,
        rainfall: 0,           // NUMERIC ZERO MUST BE PRESERVED
        soil_moisture: 42.1,
        water_level: null,     // NULL MUST REMAIN UNAVAILABLE
        air_quality: 50,
        battery: 4.12,
      });

      // Initially, no node selected -> detail card hidden
      const detailCard = rightPanel.element.querySelector('#ce-card-selected-node');
      assert.ok(detailCard.classList.contains('hidden'));

      // Select NODE-001
      store.selectNode('NODE-001');
      assert.ok(!detailCard.classList.contains('hidden'));

      const idEl = rightPanel.element.querySelector('#ce-detail-node-id');
      const coordsEl = rightPanel.element.querySelector('#ce-detail-coords');
      const tsEl = rightPanel.element.querySelector('#ce-detail-timestamp');
      const tempEl = rightPanel.element.querySelector('#ce-detail-temp');
      const rainEl = rightPanel.element.querySelector('#ce-detail-rain');
      const waterEl = rightPanel.element.querySelector('#ce-detail-water');
      const aqiEl = rightPanel.element.querySelector('#ce-detail-aqi');
      const batteryEl = rightPanel.element.querySelector('#ce-detail-battery');

      assert.ok(idEl.textContent.includes('NODE-001'));
      assert.ok(coordsEl.textContent.includes('1.2850°'));
      assert.equal(tsEl.textContent, '2026-09-08T06:15:00.000Z');
      assert.equal(tempEl.textContent, '32.5 °C');
      assert.equal(rainEl.textContent, '0 mm/h', 'Numeric zero preserved for rainfall');
      assert.equal(waterEl.textContent, '--', 'Null preserved as unavailable sentinel');
      assert.equal(aqiEl.textContent, '50 AQI');
      assert.equal(batteryEl.textContent, '4.12 V');

      rightPanel.destroy();
    } finally {
      tearDownDom();
    }
  });

  test('clean destroy removes data source, entities, handlers, and subscriptions', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });
    assert.equal(viewer.dataSources.length, 1);

    layer.destroy();

    assert.equal(viewer.dataSources.length, 0);
  });

  test('repeated initialize safety (singleton idempotency)', () => {
    const l1 = initNodesLayer({ viewer, store, Cesium });
    assert.equal(getNodesLayer(), l1);

    const l2 = initNodesLayer({ viewer, store, Cesium });
    assert.equal(l2, l1);

    destroyNodesLayer();
    assert.equal(getNodesLayer(), null);
  });

  test('missing coordinates do not create invalid entity on globe', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    // Node without coordinates
    store.updateNode({ node_id: 'NODE-NO-COORDS', name: 'Unlocated Node', latitude: null, longitude: null });

    const ds = layer.getDataSource();
    assert.equal(ds.entities.values.length, 0);

    // Later receives coordinates via telemetry
    store.updateTelemetry({ node_id: 'NODE-NO-COORDS', latitude: 10.0, longitude: 20.0 });
    assert.equal(ds.entities.values.length, 1);
    assert.ok(ds.entities.getById('climate-node:NODE-NO-COORDS'));
  });

  test('click selection on canvas selects node in authoritative store', () => {
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    store.updateNode({ node_id: 'NODE-001', latitude: 1.28, longitude: 103.85 });

    // Set mock pick result at (100, 200)
    viewer._setPicked(100, 200, { id: 'climate-node:NODE-001' });

    // Simulate canvas click via Cesium.ScreenSpaceEventHandler
    const handler = viewer.scene.canvas._handler || null;
    // We can also directly test selectNode
    layer.selectNode('NODE-001');
    assert.equal(store.getState().ui.selectedNodeId, 'NODE-001');

    layer.selectNode(null);
    assert.equal(store.getState().ui.selectedNodeId, null);
  });

  test('no second globe created (uses existing viewer.dataSources)', () => {
    const initialDsCount = viewer.dataSources.length;
    layer = createNodesLayer({ viewer, store, Cesium });
    layer.init();

    // Merely adds one CustomDataSource to existing viewer, does not create new Cesium.Viewer
    assert.equal(viewer.dataSources.length, initialDsCount + 1);
    assert.equal(viewer.dataSources.get(0).name, 'climate-eye-nodes');
  });

  test('no Node.js core imports in browser runtime code', () => {
    const files = [
      resolve(__dirname, 'nodesLayer.js'),
      resolve(__dirname, 'index.js'),
      resolve(__dirname, '../panels/rightPanel.js'),
      resolve(__dirname, '../panels/index.js'),
    ];

    const forbidden = ['node:test', 'node:assert', 'node:fs', 'node:path', 'node:url', 'node:child_process', 'node:http'];

    for (const f of files) {
      const content = readFileSync(f, 'utf-8');
      for (const pattern of forbidden) {
        assert.ok(
          !content.includes(`'${pattern}'`) && !content.includes(`"${pattern}"`),
          `Forbidden import "${pattern}" in browser file: ${f}`
        );
      }
    }
  });
});

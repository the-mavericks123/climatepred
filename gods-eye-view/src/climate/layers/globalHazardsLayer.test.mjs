/**
 * Climate Eye — Global Hazard Layer Unit Tests
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { createClimateStore, CLIMATE_LAYERS } from '../state/index.js';
import {
  createGlobalHazardsLayer,
  initGlobalHazardsLayer,
  getGlobalHazardsLayer,
  destroyGlobalHazardsLayer,
  CLIMATE_GLOBAL_HAZARDS_DATA_SOURCE_NAME,
  GLOBAL_HAZARD_ENTITY_PREFIX,
  GLOBAL_EVENT_ENTITY_PREFIX,
} from './globalHazardsLayer.js';

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
    constructor(r, g, b, a = 1.0, str = '') {
      this.r = r;
      this.g = g;
      this.b = b;
      this.a = a;
      this.str = str;
    }
    static fromCssColorString(str) {
      return new MockColor(0, 0, 0, 1, str);
    }
    withAlpha(a) {
      return new MockColor(this.r, this.g, this.b, a, this.str);
    }
  }

  MockColor.WHITE = new MockColor(1, 1, 1, 1);
  MockColor.BLACK = new MockColor(0, 0, 0, 1);
  MockColor.RED = new MockColor(1, 0, 0, 1);
  MockColor.YELLOW = new MockColor(1, 1, 0, 1);
  MockColor.PURPLE = new MockColor(0.5, 0, 0.5, 1);

  class MockEntity {
    constructor(options = {}) {
      this.id = options.id;
      this.name = options.name;
      this.position = options.position;
      this.point = options.point ? { ...options.point } : null;
      this.label = options.label ? { ...options.label } : null;
      this.ellipse = options.ellipse ? { ...options.ellipse } : null;
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
      this.show = true;
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
    removeInputAction(type) {
      this.actions.delete(type);
    }
    destroy() {
      this.actions.clear();
      this.isDestroyed = true;
    }
    trigger(type, movement) {
      const handler = this.actions.get(type);
      if (handler) handler(movement);
    }
  }

  return {
    Cartesian3: MockCartesian3,
    Cartesian2: MockCartesian2,
    Color: MockColor,
    CustomDataSource: MockCustomDataSource,
    ScreenSpaceEventHandler: MockScreenSpaceEventHandler,
    ScreenSpaceEventType: { LEFT_CLICK: 0 },
    HeightReference: { CLAMP_TO_GROUND: 1 },
    LabelStyle: { FILL_AND_OUTLINE: 2 },
  };
}

function createMockViewer(Cesium) {
  const dataSources = {
    _list: [],
    add: function (ds) {
      this._list.push(ds);
      return Promise.resolve(ds);
    },
    remove: function (ds, destroy) {
      const idx = this._list.indexOf(ds);
      if (idx !== -1) {
        this._list.splice(idx, 1);
        if (destroy && ds.entities) {
          ds.entities.removeAll();
        }
        return true;
      }
      return false;
    },
    contains: function (ds) {
      return this._list.includes(ds);
    },
  };

  const canvas = {
    addEventListener: () => {},
    removeEventListener: () => {},
  };

  const scene = {
    canvas,
    pick: (pos) => null,
  };

  const container = {
    appendChild: () => {},
    removeChild: () => {},
  };

  return {
    dataSources,
    scene,
    container,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Climate Eye — Global Hazard Layer', () => {
  let Cesium;
  let viewer;
  let store;

  beforeEach(() => {
    Cesium = createMockCesium();
    viewer = createMockViewer(Cesium);
    store = createClimateStore();
  });

  afterEach(() => {
    destroyGlobalHazardsLayer();
  });

  test('createGlobalHazardsLayer requires viewer and store', () => {
    assert.throws(() => createGlobalHazardsLayer({}), /Cesium viewer/);
    assert.throws(() => createGlobalHazardsLayer({ viewer }), /authoritative Climate Eye store/);
  });

  test('init creates a CustomDataSource and registers entities from state', () => {
    const layer = createGlobalHazardsLayer({ viewer, store, Cesium });
    layer.init();

    const ds = layer.getDataSource();
    assert.ok(ds, 'CustomDataSource created');
    assert.equal(ds.name, CLIMATE_GLOBAL_HAZARDS_DATA_SOURCE_NAME);
    assert.ok(viewer.dataSources.contains(ds), 'DataSource added to viewer');

    layer.destroy();
  });

  test('synchronizes GlobalHazardZone entities from state.global.hazards', () => {
    store.dispatch({
      type: 'GLOBAL_HAZARDS_UPDATED',
      payload: {
        hazards: [
          {
            zone_id: 'hz-heat-001',
            hazard_type: 'HEAT',
            severity: 0.85,
            confidence: 0.92,
            epistemic_status: 'OBSERVED',
            center: { latitude: 28.6139, longitude: 77.2090 },
            radius_km: 25.0,
            source: 'open_meteo',
            timestamp: '2026-09-08T06:00:00Z',
            affected_population: 1500000,
            recommended_action: 'Issue Heatwave Level 3 Red Alert',
          },
          {
            zone_id: 'hz-flood-002',
            hazard_type: 'FLOOD',
            severity: 0.75,
            confidence: 0.88,
            epistemic_status: 'OBSERVED',
            center: { latitude: 23.8103, longitude: 90.4125 },
            radius_km: 40.0,
            source: 'gdacs',
            timestamp: '2026-09-08T06:00:00Z',
            affected_population: 850000,
            recommended_action: 'Reinforce river embankments and initiate evacuations',
          },
        ],
      },
    });

    const layer = createGlobalHazardsLayer({ viewer, store, Cesium });
    layer.init();

    const entities = layer.getDataSource().entities.values;
    assert.equal(entities.length, 2, 'Should create 2 hazard entities');

    const heat = layer.getDataSource().entities.getById(`${GLOBAL_HAZARD_ENTITY_PREFIX}hz-heat-001`);
    assert.ok(heat, 'Heat hazard entity created');
    assert.equal(heat.ellipse.semiMajorAxis, 25000);
    assert.equal(heat.properties.hazard_type, 'HEAT');
    assert.equal(heat.properties.severity, 0.85);

    const flood = layer.getDataSource().entities.getById(`${GLOBAL_HAZARD_ENTITY_PREFIX}hz-flood-002`);
    assert.ok(flood, 'Flood hazard entity created');
    assert.equal(flood.ellipse.semiMajorAxis, 40000);

    layer.destroy();
  });

  test('synchronizes GlobalDisasterEvent entities from state.global.events', () => {
    store.dispatch({
      type: 'GLOBAL_EVENTS_UPDATED',
      payload: {
        events: [
          {
            event_id: 'ev-usgs-1234',
            event_type: 'EARTHQUAKE',
            title: 'M6.2 Northern Sumatra',
            severity: 0.78,
            alert_level: 'ORANGE',
            confidence: 1.0,
            location: { latitude: 2.1, longitude: 98.5 },
            affected_radius_km: 50.0,
            source: 'usgs',
            timestamp: '2026-09-08T05:30:00Z',
          },
        ],
      },
    });

    const layer = createGlobalHazardsLayer({ viewer, store, Cesium });
    layer.init();

    const eq = layer.getDataSource().entities.getById(`${GLOBAL_EVENT_ENTITY_PREFIX}ev-usgs-1234`);
    assert.ok(eq, 'Earthquake disaster entity created');
    assert.equal(eq.properties.hazard_type, 'EARTHQUAKE');
    assert.equal(eq.ellipse.semiMajorAxis, 50000);

    layer.destroy();
  });

  test('synchronizes CompoundEvent cascades from state.compound.events', () => {
    store.dispatch({
      type: 'COMPOUND_UPDATED',
      payload: {
        events: [
          {
            compound_id: 'cmp-heat-drought-01',
            name: 'Severe Heatwave + Flash Drought',
            hazard_types: ['HEAT', 'DROUGHT'],
            cascade_probability: 0.88,
            primary_location: { latitude: 35.0, longitude: -115.0 },
          },
        ],
      },
    });

    const layer = createGlobalHazardsLayer({ viewer, store, Cesium });
    layer.init();

    const cmp = layer.getDataSource().entities.getById(`${GLOBAL_HAZARD_ENTITY_PREFIX}compound-cmp-heat-drought-01`);
    assert.ok(cmp, 'Compound event entity created');
    assert.equal(cmp.properties.hazard_type, 'COMPOUND');

    layer.destroy();
  });

  test('respects layer visibility toggles', () => {
    store.dispatch({
      type: 'GLOBAL_HAZARDS_UPDATED',
      payload: {
        hazards: [
          {
            zone_id: 'hz-heat-001',
            hazard_type: 'HEAT',
            center: { latitude: 10, longitude: 20 },
            radius_km: 10,
          },
        ],
      },
    });

    const layer = createGlobalHazardsLayer({ viewer, store, Cesium });
    layer.init();

    assert.equal(layer.getDataSource().show, true);

    // Toggle master visibility off
    layer.setVisible(false);
    assert.equal(layer.getDataSource().show, false);

    layer.setVisible(true);
    assert.equal(layer.getDataSource().show, true);

    layer.destroy();
  });

  test('singleton lifecycle idempotency', () => {
    const l1 = initGlobalHazardsLayer({ viewer, store, Cesium });
    const l2 = initGlobalHazardsLayer({ viewer, store, Cesium });
    assert.equal(l1, l2, 'Singleton returns same instance');
    assert.equal(getGlobalHazardsLayer(), l1);

    destroyGlobalHazardsLayer();
    assert.equal(getGlobalHazardsLayer(), null);
  });

  test('browser-safe runtime code: no Node.js core modules imported', () => {
    const filePath = resolve(__dirname, 'globalHazardsLayer.js');
    const content = readFileSync(filePath, 'utf8');

    assert.ok(!content.includes("from 'node:"), 'Must not import node:* modules');
    assert.ok(!content.includes("require('node:"), 'Must not require node:* modules');
    assert.ok(!content.includes("from 'fs'"), 'Must not import fs');
    assert.ok(!content.includes("from 'path'"), 'Must not import path');
  });
});

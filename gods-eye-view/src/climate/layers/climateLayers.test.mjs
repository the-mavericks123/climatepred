/**
 * Climate Eye — Climate Data Visualization Layers Test Suite (Step F4.5)
 *
 * Validates:
 * 1. Canonical layer definitions & constants (all 9 layers)
 * 2. State management for layer visibility
 * 3. Non-risk layer legend metadata and provenance attribution
 * 4. Telemetry metric layer rendering (Temperature, Rainfall, Soil Moisture, Air Quality, Water Level)
 * 5. Strict numeric 0 preservation (0 mm/h, 0%, etc.)
 * 6. Strict null preservation (-- without false zeroing)
 * 7. In-place metric update without entity recreation
 * 8. Dynamic layer toggling (showing/hiding updates entity set)
 * 9. SENSOR_MESH visibility toggling
 * 10. GEV NASA FIRMS adapter integration (local-firms)
 * 11. GEV USACE Dams adapter integration (local-dams)
 * 12. GEV USGS Earthquakes adapter integration (earthquakes)
 * 13. Adapter fallback behavior when dataManager is absent
 * 14. Controller lifecycle: clean init and leak-free destruction
 * 15. Zero risk calculation boundary enforcement
 * 16. Browser-safe code verification (no Node.js core modules in browser assets)
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  createClimateStore,
  CLIMATE_LAYERS,
  ACTION_TYPES,
} from '../state/index.js';

import {
  LAYER_LEGENDS,
  getLayerLegend,
  formatMeasurementBadge,
  createMetricLayers,
  createFirmsAdapter,
  createDamsAdapter,
  createEarthquakesAdapter,
  createLayersController,
  initClimateLayers,
  getClimateLayers,
  destroyClimateLayers,
  CLIMATE_METRIC_ENTITY_PREFIX,
} from './index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Mock Cesium & DOM Environment for Unit Tests
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
    constructor(r = 0, g = 0, b = 0, a = 1.0) {
      this.r = r;
      this.g = g;
      this.b = b;
      this.a = a;
    }
    static fromCssColorString(str) {
      return new MockColor(0, 0, 0, 1);
    }
  }
  MockColor.WHITE = new MockColor(1, 1, 1, 1);
  MockColor.BLACK = new MockColor(0, 0, 0, 1);

  class MockEntity {
    constructor(options = {}) {
      this.id = options.id;
      this.name = options.name;
      this.position = options.position;
      this.label = options.label ? {
        text: options.label.text,
        pixelOffset: options.label.pixelOffset,
        fillColor: options.label.fillColor,
      } : null;
      this.point = options.point ? { ...options.point } : null;
      this.properties = options.properties ? { ...options.properties } : {};
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
    remove(entity) {
      if (!entity) return false;
      const id = typeof entity === 'string' ? entity : entity.id;
      return this._entities.delete(id);
    }
    removeAll() {
      this._entities.clear();
    }
    getById(id) {
      return this._entities.get(id) || null;
    }
  }

  class MockCustomDataSource {
    constructor(name) {
      this.name = name;
      this.show = true;
      this.entities = new MockEntityCollection();
    }
  }

  return {
    Cartesian3: MockCartesian3,
    Cartesian2: MockCartesian2,
    Color: MockColor,
    Entity: MockEntity,
    CustomDataSource: MockCustomDataSource,
    HeightReference: { CLAMP_TO_GROUND: 1 },
    LabelStyle: { FILL_AND_OUTLINE: 2 },
  };
}

function createMockViewer(mockCesium) {
  const dataSourcesList = [];
  return {
    dataSources: {
      add: (ds) => {
        dataSourcesList.push(ds);
        return ds;
      },
      remove: (ds) => {
        const idx = dataSourcesList.indexOf(ds);
        if (idx !== -1) {
          dataSourcesList.splice(idx, 1);
          return true;
        }
        return false;
      },
      contains: (ds) => dataSourcesList.includes(ds),
      get length() {
        return dataSourcesList.length;
      },
      _list: dataSourcesList,
    },
    scene: {
      canvas: {},
      pick: () => null,
    },
  };
}

function createMockDataManager() {
  const enabledLayers = new Set();
  const layerEntries = new Map();

  return {
    layers: layerEntries,
    isEnabled: (id) => enabledLayers.has(id),
    setEnabled: async (id, enabled) => {
      if (enabled) enabledLayers.add(id);
      else enabledLayers.delete(id);
      return enabled;
    },
    toggle: async (id) => {
      const next = !enabledLayers.has(id);
      if (next) enabledLayers.add(id);
      else enabledLayers.delete(id);
      return next;
    },
    _enabledLayers: enabledLayers,
  };
}

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe('Frontend Step F4.5: Climate Data Visualization Layers', () => {

  describe('1. Canonical Layer Definitions & Constants', () => {
    test('defines all 9 required Climate Eye layer keys', () => {
      const required = [
        'SENSOR_MESH',
        'TEMPERATURE',
        'RAINFALL',
        'SOIL_MOISTURE',
        'AIR_QUALITY',
        'WATER_LEVEL',
        'FIRES',
        'DAMS',
        'EARTHQUAKES',
      ];
      for (const key of required) {
        assert.ok(CLIMATE_LAYERS[key], `CLIMATE_LAYERS must contain ${key}`);
        assert.equal(CLIMATE_LAYERS[key], key);
      }
    });

    test('defines LAYER_VISIBILITY_CHANGED in ACTION_TYPES', () => {
      assert.equal(ACTION_TYPES.LAYER_VISIBILITY_CHANGED, 'LAYER_VISIBILITY_CHANGED');
    });
  });

  describe('2. State Management for Layer Visibility', () => {
    test('initial state defaults SENSOR_MESH and TEMPERATURE to true, others to false', () => {
      const store = createClimateStore();
      const state = store.getState();
      assert.ok(state.layers, 'layers state branch must exist');
      assert.equal(state.layers[CLIMATE_LAYERS.SENSOR_MESH], true);
      assert.equal(state.layers[CLIMATE_LAYERS.TEMPERATURE], true);
      assert.equal(state.layers[CLIMATE_LAYERS.RAINFALL], false);
      assert.equal(state.layers[CLIMATE_LAYERS.SOIL_MOISTURE], false);
      assert.equal(state.layers[CLIMATE_LAYERS.AIR_QUALITY], false);
      assert.equal(state.layers[CLIMATE_LAYERS.WATER_LEVEL], false);
      assert.equal(state.layers[CLIMATE_LAYERS.FIRES], false);
      assert.equal(state.layers[CLIMATE_LAYERS.DAMS], false);
      assert.equal(state.layers[CLIMATE_LAYERS.EARTHQUAKES], false);
    });

    test('setLayerVisibility updates store state immutably', () => {
      const store = createClimateStore();
      store.setLayerVisibility(CLIMATE_LAYERS.RAINFALL, true);
      assert.equal(store.getState().layers[CLIMATE_LAYERS.RAINFALL], true);

      store.setLayerVisibility(CLIMATE_LAYERS.RAINFALL, false);
      assert.equal(store.getState().layers[CLIMATE_LAYERS.RAINFALL], false);
    });

    test('toggleLayer flips layer visibility', () => {
      const store = createClimateStore();
      assert.equal(store.isLayerVisible(CLIMATE_LAYERS.SOIL_MOISTURE), false);

      store.toggleLayer(CLIMATE_LAYERS.SOIL_MOISTURE);
      assert.equal(store.isLayerVisible(CLIMATE_LAYERS.SOIL_MOISTURE), true);

      store.toggleLayer(CLIMATE_LAYERS.SOIL_MOISTURE);
      assert.equal(store.isLayerVisible(CLIMATE_LAYERS.SOIL_MOISTURE), false);
    });
  });

  describe('3. Non-Risk Layer Legends & Attribution', () => {
    test('all 9 layers have complete non-risk legend definitions', () => {
      for (const [key, layerId] of Object.entries(CLIMATE_LAYERS)) {
        const legend = getLayerLegend(layerId);
        assert.ok(legend, `Legend must exist for ${key}`);
        assert.equal(legend.id, layerId);
        assert.ok(legend.title, `Legend must have a title`);
        assert.ok(legend.unit, `Legend must define a physical unit`);
        assert.ok(legend.metric, `Legend must define metric field`);
        assert.ok(legend.source, `Legend must define source attribution`);
        assert.equal(legend.isRiskLayer, false, 'Layer must be strictly non-risk');
        assert.ok(legend.notice, 'Legend must contain non-risk notice');
      }
    });

    test('legends contain physical units and disclaim risk inference', () => {
      assert.equal(LAYER_LEGENDS[CLIMATE_LAYERS.TEMPERATURE].unit, '°C');
      assert.equal(LAYER_LEGENDS[CLIMATE_LAYERS.RAINFALL].unit, 'mm/h');
      assert.equal(LAYER_LEGENDS[CLIMATE_LAYERS.SOIL_MOISTURE].unit, '%');
      assert.equal(LAYER_LEGENDS[CLIMATE_LAYERS.AIR_QUALITY].unit, 'AQI');
      assert.equal(LAYER_LEGENDS[CLIMATE_LAYERS.WATER_LEVEL].unit, 'm');

      // Notices explicitly state no risk scores
      assert.match(LAYER_LEGENDS[CLIMATE_LAYERS.TEMPERATURE].notice, /no.*risk/i);
      assert.match(LAYER_LEGENDS[CLIMATE_LAYERS.RAINFALL].notice, /no.*inference/i);
    });
  });

  describe('4. Telemetry Metric Formatting & Value Preservation', () => {
    test('formatMeasurementBadge preserves numeric 0 strictly', () => {
      assert.equal(formatMeasurementBadge(0, 'mm/h', 1), '0.0 mm/h');
      assert.equal(formatMeasurementBadge(0, '%', 1), '0.0 %');
      assert.equal(formatMeasurementBadge(0, '°C', 1), '0.0 °C');
      assert.equal(formatMeasurementBadge(0, 'AQI', 0), '0 AQI');
    });

    test('formatMeasurementBadge preserves null or undefined as placeholder --', () => {
      assert.equal(formatMeasurementBadge(null, 'mm/h', 1), '-- mm/h');
      assert.equal(formatMeasurementBadge(undefined, '%', 1), '-- %');
      assert.equal(formatMeasurementBadge(NaN, '°C', 1), '-- °C');
    });

    test('formatMeasurementBadge formats positive and negative numbers correctly', () => {
      assert.equal(formatMeasurementBadge(28.6, '°C', 1), '28.6 °C');
      assert.equal(formatMeasurementBadge(-4.2, '°C', 1), '-4.2 °C');
      assert.equal(formatMeasurementBadge(12.75, 'm', 2), '12.75 m');
    });
  });

  describe('5. Telemetry Metric Layers Rendering', () => {
    let mockCesium;
    let mockViewer;
    let store;

    beforeEach(() => {
      mockCesium = createMockCesium();
      mockViewer = createMockViewer(mockCesium);
      store = createClimateStore();
    });

    test('renders metric badges for active layers and valid node coordinates', () => {
      // Enable temperature and rainfall
      store.setLayerVisibility(CLIMATE_LAYERS.TEMPERATURE, true);
      store.setLayerVisibility(CLIMATE_LAYERS.RAINFALL, true);

      // Add node and telemetry
      store.updateNode({ node_id: 'NODE-001', latitude: 19.076, longitude: 72.877 });
      store.updateTelemetry({
        node_id: 'NODE-001',
        temperature: 31.2,
        rainfall: 0, // 0 mm/h must be preserved
      });

      const metricsLayer = createMetricLayers({
        viewer: mockViewer,
        store,
        Cesium: mockCesium,
      });
      metricsLayer.init();

      const ds = metricsLayer.getDataSource();
      assert.ok(ds, 'Metric data source must be created');
      const entities = ds.entities.values;

      // Expect 2 entities: 1 for temperature, 1 for rainfall
      assert.equal(entities.length, 2);

      const tempEntity = ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}TEMPERATURE:NODE-001`);
      assert.ok(tempEntity, 'Temperature badge entity must exist');
      assert.equal(tempEntity.label.text, '31.2 °C');

      const rainEntity = ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}RAINFALL:NODE-001`);
      assert.ok(rainEntity, 'Rainfall badge entity must exist');
      assert.equal(rainEntity.label.text, '0.0 mm/h', '0 mm/h must be strictly preserved');

      metricsLayer.destroy();
    });

    test('updates existing entity in place on telemetry update without recreation', () => {
      store.setLayerVisibility(CLIMATE_LAYERS.TEMPERATURE, true);
      store.updateNode({ node_id: 'NODE-001', latitude: 19.076, longitude: 72.877 });
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 25.0 });

      const metricsLayer = createMetricLayers({
        viewer: mockViewer,
        store,
        Cesium: mockCesium,
      });
      metricsLayer.init();

      const ds = metricsLayer.getDataSource();
      const entityBefore = ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}TEMPERATURE:NODE-001`);
      assert.equal(entityBefore.label.text, '25.0 °C');

      // Update telemetry
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 28.5 });

      const entityAfter = ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}TEMPERATURE:NODE-001`);
      assert.strictEqual(entityBefore, entityAfter, 'Entity reference must be preserved (in-place update)');
      assert.equal(entityAfter.label.text, '28.5 °C');

      metricsLayer.destroy();
    });

    test('deactivating a metric layer removes its entities from the data source', () => {
      store.setLayerVisibility(CLIMATE_LAYERS.TEMPERATURE, true);
      store.setLayerVisibility(CLIMATE_LAYERS.RAINFALL, true);
      store.updateNode({ node_id: 'NODE-001', latitude: 19.076, longitude: 72.877 });
      store.updateTelemetry({ node_id: 'NODE-001', temperature: 25.0, rainfall: 4.5 });

      const metricsLayer = createMetricLayers({
        viewer: mockViewer,
        store,
        Cesium: mockCesium,
      });
      metricsLayer.init();

      const ds = metricsLayer.getDataSource();
      assert.equal(ds.entities.values.length, 2);

      // Turn off rainfall layer
      store.setLayerVisibility(CLIMATE_LAYERS.RAINFALL, false);
      assert.equal(ds.entities.values.length, 1);
      assert.equal(ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}RAINFALL:NODE-001`), null);
      assert.ok(ds.entities.getById(`${CLIMATE_METRIC_ENTITY_PREFIX}TEMPERATURE:NODE-001`));

      metricsLayer.destroy();
    });
  });

  describe('6. GEV Adapters (FIRMS, Dams, Earthquakes)', () => {
    let mockDataManager;
    let mockViewer;

    beforeEach(() => {
      mockDataManager = createMockDataManager();
      mockViewer = createMockViewer(createMockCesium());
    });

    test('NASA FIRMS adapter delegates visibility to local-firms in dataManager', async () => {
      const adapter = createFirmsAdapter({ dataManager: mockDataManager, viewer: mockViewer });
      assert.equal(adapter.isVisible(), false);

      await adapter.setVisible(true);
      assert.equal(adapter.isVisible(), true);
      assert.ok(mockDataManager._enabledLayers.has('local-firms'));

      await adapter.setVisible(false);
      assert.equal(adapter.isVisible(), false);
      assert.ok(!mockDataManager._enabledLayers.has('local-firms'));

      adapter.destroy();
    });

    test('USACE Dams adapter delegates visibility to local-dams in dataManager', async () => {
      const adapter = createDamsAdapter({ dataManager: mockDataManager, viewer: mockViewer });
      assert.equal(adapter.isVisible(), false);

      await adapter.setVisible(true);
      assert.equal(adapter.isVisible(), true);
      assert.ok(mockDataManager._enabledLayers.has('local-dams'));

      adapter.destroy();
    });

    test('USGS Earthquakes adapter delegates visibility to earthquakes in dataManager', async () => {
      const adapter = createEarthquakesAdapter({ dataManager: mockDataManager, viewer: mockViewer });
      assert.equal(adapter.isVisible(), false);

      await adapter.setVisible(true);
      assert.equal(adapter.isVisible(), true);
      assert.ok(mockDataManager._enabledLayers.has('earthquakes'));

      adapter.destroy();
    });

    test('adapters handle absent dataManager gracefully without throwing', async () => {
      const adapter = createFirmsAdapter({ dataManager: null, viewer: mockViewer });
      assert.equal(adapter.isVisible(), false);
      const result = await adapter.setVisible(true);
      assert.equal(result, false);
      assert.doesNotThrow(() => adapter.destroy());
    });
  });

  describe('7. Unified Layers Controller Lifecycle', () => {
    let mockCesium;
    let mockViewer;
    let mockDataManager;
    let store;

    beforeEach(() => {
      mockCesium = createMockCesium();
      mockViewer = createMockViewer(mockCesium);
      mockDataManager = createMockDataManager();
      store = createClimateStore();
    });

    afterEach(() => {
      destroyClimateLayers();
    });

    test('initClimateLayers initializes all layers and synchronizes with store', () => {
      const controller = initClimateLayers({
        viewer: mockViewer,
        store,
        dataManager: mockDataManager,
        Cesium: mockCesium,
      });

      assert.ok(controller, 'Controller instance must exist');
      assert.equal(getClimateLayers(), controller, 'Singleton getter must return active instance');

      // SENSOR_MESH and TEMPERATURE are enabled by default
      assert.equal(controller.isLayerVisible(CLIMATE_LAYERS.SENSOR_MESH), true);
      assert.equal(controller.isLayerVisible(CLIMATE_LAYERS.TEMPERATURE), true);

      // Toggling layer via controller updates store
      controller.toggleLayer(CLIMATE_LAYERS.RAINFALL);
      assert.equal(store.isLayerVisible(CLIMATE_LAYERS.RAINFALL), true);

      // Toggling FIRMS updates GEV dataManager
      controller.setLayerVisibility(CLIMATE_LAYERS.FIRES, true);
      assert.equal(store.isLayerVisible(CLIMATE_LAYERS.FIRES), true);
      assert.ok(mockDataManager._enabledLayers.has('local-firms'));

      destroyClimateLayers();
      assert.equal(getClimateLayers(), null);
    });

    test('idempotent initialization returns existing active instance', () => {
      const first = initClimateLayers({ viewer: mockViewer, store, Cesium: mockCesium });
      const second = initClimateLayers({ viewer: mockViewer, store, Cesium: mockCesium });
      assert.strictEqual(first, second, 'Subsequent init must return active singleton');
      destroyClimateLayers();
    });
  });

  describe('8. Browser-Safe Runtime Verification', () => {
    const files = [
      'legends.js',
      'metricLayers.js',
      'layersController.js',
      'adapters/firmsAdapter.js',
      'adapters/damsAdapter.js',
      'adapters/earthquakesAdapter.js',
    ];

    for (const file of files) {
      test(`${file} contains no Node.js built-in modules`, () => {
        const filePath = resolve(__dirname, file);
        const content = readFileSync(filePath, 'utf-8');

        assert.doesNotMatch(content, /from\s+['"]node:/, `${file} must not import node: modules`);
        assert.doesNotMatch(content, /require\s*\(['"]node:/, `${file} must not require node: modules`);
        assert.doesNotMatch(content, /from\s+['"]fs['"]/, `${file} must not import fs`);
        assert.doesNotMatch(content, /from\s+['"]path['"]/, `${file} must not import path`);
      });
    }
  });
});

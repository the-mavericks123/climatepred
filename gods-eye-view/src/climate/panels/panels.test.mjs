/**
 * Climate Eye — Command Center Panels Unit Tests (Step F4.1)
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  CLIMATE_MODES,
  REALTIME_STATES,
  ACTION_TYPES,
  createClimateStore,
} from '../state/index.js';

import {
  mountClimateShell,
  initClimateShell,
  destroyClimateShell,
  getClimateShell,
  createTopNav,
  createLeftPanel,
  createRightPanel,
  createStatusBar,
} from './index.js';

// ---------------------------------------------------------------------------
// Minimal DOM Mock for Node.js Testing Environment
// ---------------------------------------------------------------------------

function createMockElement(tagName = 'div') {
  const children = [];
  const attributes = new Map();
  const listeners = new Map();
  let _innerHTML = '';
  let _className = '';
  let _id = '';
  let _rel = '';
  let _href = '';
  const classListSet = new Set();

  function syncClassListFromClassName() {
    classListSet.clear();
    _className
      .split(/\s+/)
      .filter(Boolean)
      .forEach((c) => classListSet.add(c));
  }

  const element = {
    tagName: tagName.toUpperCase(),
    children,

    get id() {
      return _id;
    },
    set id(val) {
      _id = String(val);
      attributes.set('id', _id);
    },

    get rel() {
      return _rel;
    },
    set rel(val) {
      _rel = String(val);
      attributes.set('rel', _rel);
    },

    get href() {
      return _href;
    },
    set href(val) {
      _href = String(val);
      attributes.set('href', _href);
    },

    get className() {
      return _className;
    },
    set className(val) {
      _className = String(val);
      attributes.set('class', _className);
      syncClassListFromClassName();
    },

    style: {},

    get classList() {
      return {
        add: (...cls) => {
          cls.forEach((c) => classListSet.add(c));
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
        },
        remove: (...cls) => {
          cls.forEach((c) => classListSet.delete(c));
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
        },
        toggle: (c, force) => {
          if (force === true) {
            classListSet.add(c);
          } else if (force === false) {
            classListSet.delete(c);
          } else if (classListSet.has(c)) {
            classListSet.delete(c);
          } else {
            classListSet.add(c);
          }
          _className = Array.from(classListSet).join(' ');
          attributes.set('class', _className);
          return classListSet.has(c);
        },
        contains: (c) => classListSet.has(c),
      };
    },

    setAttribute: (name, value) => {
      const strVal = String(value);
      attributes.set(name, strVal);
      if (name === 'id') _id = strVal;
      if (name === 'class') {
        _className = strVal;
        syncClassListFromClassName();
      }
      if (name === 'rel') _rel = strVal;
      if (name === 'href') _href = strVal;
    },
    getAttribute: (name) => {
      if (name === 'id') return _id || attributes.get('id') || null;
      if (name === 'class') return _className || attributes.get('class') || null;
      if (name === 'rel') return _rel || attributes.get('rel') || null;
      if (name === 'href') return _href || attributes.get('href') || null;
      return attributes.get(name) || null;
    },
    hasAttribute: (name) => attributes.has(name),

    appendChild: (child) => {
      children.push(child);
      child.parentNode = element;
      return child;
    },
    remove: () => {
      if (element.parentNode && element.parentNode.children) {
        const idx = element.parentNode.children.indexOf(element);
        if (idx !== -1) element.parentNode.children.splice(idx, 1);
      }
    },

    addEventListener: (type, fn) => {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
    removeEventListener: (type, fn) => {
      if (!listeners.has(type)) return;
      const arr = listeners.get(type).filter((f) => f !== fn);
      listeners.set(type, arr);
    },
    dispatchEvent: (event) => {
      const type = event.type || event;
      const fns = listeners.get(type) || [];
      fns.forEach((fn) => fn.call(element, { ...event, target: element }));
    },

    click: () => {
      element.dispatchEvent({ type: 'click' });
    },

    get innerHTML() {
      return _innerHTML;
    },
    set innerHTML(html) {
      _innerHTML = html;
      children.length = 0;
      parseHTMLStack(html, element);
    },

    get textContent() {
      let text = '';
      function walk(el) {
        if (el._text) text += el._text;
        if (el.children) el.children.forEach(walk);
      }
      walk(element);
      return text;
    },
    set textContent(val) {
      children.length = 0;
      element._text = String(val);
    },

    querySelector: (selector) => {
      return querySelectorAllDeep(element, selector)[0] || null;
    },
    querySelectorAll: (selector) => {
      return querySelectorAllDeep(element, selector);
    },
    closest: (selector) => {
      let curr = element;
      while (curr) {
        if (matchesSelector(curr, selector)) return curr;
        curr = curr.parentNode;
      }
      return null;
    },
  };

  return element;
}

/** Stack-based HTML parser handling nested identical tags like <span><span>...</span></span> */
function parseHTMLStack(html, root) {
  const stack = [root];
  // Matches comments, closing tags, self-closing tags, or opening tags
  const tokenRegex = /<!--[\s\S]*?-->|<\/([a-zA-Z0-9-]+)>|<([a-zA-Z0-9-]+)([^>]*?)(\/?)>|([^<]+)/g;
  const voidTags = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);

  let match;
  while ((match = tokenRegex.exec(html)) !== null) {
    const [full, closeTag, openTag, attrStr, selfClose, text] = match;

    if (full.startsWith('<!--')) {
      continue; // skip comment
    }

    if (closeTag) {
      // Find matching tag in stack
      const lower = closeTag.toLowerCase();
      for (let i = stack.length - 1; i > 0; i--) {
        if (stack[i].tagName.toLowerCase() === lower) {
          stack.length = i;
          break;
        }
      }
    } else if (openTag) {
      const el = createMockElement(openTag);
      // Parse attributes
      const attrRegex = /([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g;
      let aMatch;
      while ((aMatch = attrRegex.exec(attrStr || '')) !== null) {
        el.setAttribute(aMatch[1], aMatch[2] !== undefined ? aMatch[2] : '');
      }

      const parent = stack[stack.length - 1];
      if (parent) {
        parent.appendChild(el);
      }

      const isVoid = voidTags.has(openTag.toLowerCase()) || selfClose === '/';
      if (!isVoid) {
        stack.push(el);
      }
    } else if (text && text.trim()) {
      const parent = stack[stack.length - 1];
      if (parent) {
        const textNode = createMockElement('#text');
        textNode._text = text;
        parent.appendChild(textNode);
      }
    }
  }
}

function matchesSelector(el, selector) {
  if (!el || !selector) return false;
  selector = selector.trim();
  if (selector.startsWith('#')) {
    return el.id === selector.slice(1);
  }
  if (selector.startsWith('.')) {
    return el.classList.contains(selector.slice(1));
  }
  if (selector.startsWith('[') && selector.endsWith(']')) {
    const attrMatch = selector.slice(1, -1).match(/([a-zA-Z0-9_-]+)(?:="([^"]*)")?/);
    if (attrMatch) {
      const [, attrName, attrVal] = attrMatch;
      if (attrVal !== undefined) {
        return el.getAttribute(attrName) === attrVal;
      }
      return el.hasAttribute(attrName);
    }
  }
  return el.tagName.toLowerCase() === selector.toLowerCase();
}

function querySelectorAllDeep(root, selector) {
  const results = [];
  function walk(node) {
    if (!node || !node.children) return;
    for (const child of node.children) {
      if (matchesSelector(child, selector)) {
        results.push(child);
      }
      walk(child);
    }
  }
  walk(root);
  return results;
}

// ---------------------------------------------------------------------------
// Test Environment Setup
// ---------------------------------------------------------------------------

let originalDocument;

beforeEach(() => {
  originalDocument = globalThis.document;

  const mockHead = createMockElement('head');
  const mockBody = createMockElement('body');

  globalThis.document = {
    head: mockHead,
    body: mockBody,
    createElement: (tag) => createMockElement(tag),
    getElementById: (id) => {
      const fromBody = querySelectorAllDeep(mockBody, `#${id}`)[0];
      if (fromBody) return fromBody;
      return querySelectorAllDeep(mockHead, `#${id}`)[0] || null;
    },
    querySelector: (selector) => mockBody.querySelector(selector),
    querySelectorAll: (selector) => mockBody.querySelectorAll(selector),
  };
});

afterEach(() => {
  destroyClimateShell();
  globalThis.document = originalDocument;
});

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe('Frontend Step F4.1: Climate Eye Command-Center Shell', () => {

  describe('1. Shell Assembly & Mounting', () => {
    test('mountClimateShell creates root container with all 4 visual regions', () => {
      const store = createClimateStore();
      const shell = mountClimateShell(document.body, { store });

      assert.ok(shell.root, 'shell root must exist');
      assert.equal(shell.root.id, 'climate-eye-root');

      // 1. Top navigation
      const topNav = shell.root.querySelector('#climate-top-nav');
      assert.ok(topNav, 'top navigation must be mounted');

      // 2. Left climate panel
      const leftPanel = shell.root.querySelector('#climate-left-panel');
      assert.ok(leftPanel, 'left climate panel must be mounted');

      // 3. Right intelligence panel
      const rightPanel = shell.root.querySelector('#climate-right-panel');
      assert.ok(rightPanel, 'right intelligence panel must be mounted');

      // 4. Bottom status bar
      const statusBar = shell.root.querySelector('#climate-bottom-bar');
      assert.ok(statusBar, 'bottom status bar must be mounted');

      shell.destroy();
    });

    test('initClimateShell manages a singleton shell instance and destroy cleans up', () => {
      const store = createClimateStore();
      const shell1 = initClimateShell({ store });
      const shell2 = initClimateShell({ store });

      assert.equal(shell1, shell2, 'initClimateShell must return the singleton instance');
      assert.equal(getClimateShell(), shell1);

      destroyClimateShell();
      assert.equal(getClimateShell(), null, 'shell must be null after destroy');
    });

    test('ensureClimateStyles injects stylesheet into document head without duplication', () => {
      const store = createClimateStore();
      const shell = mountClimateShell(document.body, { store });

      const link = document.getElementById('climate-eye-shell-css');
      assert.ok(link, 'stylesheet link should be injected');
      assert.equal(link.getAttribute('rel'), 'stylesheet');

      // Second call should not duplicate
      const shell2 = mountClimateShell(document.body, { store });
      const links = document.head.querySelectorAll('#climate-eye-shell-css');
      assert.equal(links.length, 1, 'stylesheet link must not be duplicated');

      shell.destroy();
    });
  });

  describe('2. Top Navigation & Operating Modes', () => {
    test('renders CLIMATIC EYE branding and all 7 mode tabs', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const brand = topNav.element.querySelector('.ce-brand-title');
      assert.ok(brand);
      assert.match(brand.textContent, /CLIMAT(IC|E) EYE/);

      const requiredModes = [
        CLIMATE_MODES.LIVE,
        CLIMATE_MODES.ANALYTICS,
        CLIMATE_MODES.RISK,
        CLIMATE_MODES.SIMULATION,
        CLIMATE_MODES.SENSOR_MESH,
        CLIMATE_MODES.AI,
        CLIMATE_MODES.EMERGENCY,
      ];

      for (const mode of requiredModes) {
        const btn = topNav.element.querySelector(`[data-mode="${mode}"]`);
        assert.ok(btn, `Mode button for ${mode} must exist`);
      }

      topNav.destroy();
    });

    test('mode tab defaults to LIVE and clicking updates store UI mode', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const liveBtn = topNav.element.querySelector(`[data-mode="${CLIMATE_MODES.LIVE}"]`);
      assert.ok(liveBtn.classList.contains('active'), 'LIVE mode should be active by default');

      const riskBtn = topNav.element.querySelector(`[data-mode="${CLIMATE_MODES.RISK}"]`);
      riskBtn.click();

      assert.equal(store.getState().ui.mode, CLIMATE_MODES.RISK, 'Store mode must update to RISK');
      assert.ok(riskBtn.classList.contains('active'), 'RISK button must become active');
      assert.equal(liveBtn.classList.contains('active'), false, 'LIVE button must no longer be active');

      topNav.destroy();
    });

    test('external store mode dispatch updates active tab in UI', () => {
      const store = createClimateStore();
      const topNav = createTopNav(store);

      const simBtn = topNav.element.querySelector(`[data-mode="${CLIMATE_MODES.SIMULATION}"]`);
      assert.equal(simBtn.classList.contains('active'), false);

      store.setUiMode(CLIMATE_MODES.SIMULATION);
      assert.ok(simBtn.classList.contains('active'), 'SIMULATION button must be active after store update');

      topNav.destroy();
    });
  });

  describe('3. Left Climate Panel & Metric Channels', () => {
    test('renders Climate Layers, Sensors, and all 4 Metric Channels', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);

      // Section cards
      assert.ok(leftPanel.element.querySelector('#ce-card-layers'), 'Layers card must exist');
      assert.ok(leftPanel.element.querySelector('#ce-card-sensors'), 'Sensors card must exist');
      assert.ok(leftPanel.element.querySelector('#ce-card-metrics'), 'Metrics card must exist');

      // Metric labels
      const metricsCard = leftPanel.element.querySelector('#ce-card-metrics');
      assert.match(metricsCard.textContent, /TEMPERATURE \/ HEAT/);
      assert.match(metricsCard.textContent, /RAIN \/ FLOOD/);
      assert.match(metricsCard.textContent, /SOIL \/ DROUGHT/);
      assert.match(metricsCard.textContent, /AIR QUALITY/);

      leftPanel.destroy();
    });

    test('metrics explicitly show UNAVAILABLE badges when no live data is present', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);

      const unavailableBadges = leftPanel.element.querySelectorAll('.ce-unavailable-badge');
      assert.ok(unavailableBadges.length >= 4, 'Must show UNAVAILABLE badges for metric channels without data');

      const tempVal = leftPanel.element.querySelector('#ce-temp-value');
      assert.equal(tempVal.textContent, '--', 'Temperature should be placeholder --');

      leftPanel.destroy();
    });

    test('updates sensor count badge when nodes are added to the store', () => {
      const store = createClimateStore();
      const leftPanel = createLeftPanel(store);

      const badge = leftPanel.element.querySelector('#ce-sensor-count-badge');
      assert.equal(badge.textContent, '0 NODES');

      store.updateNodes([
        { node_id: 'NODE-001', latitude: 10, longitude: 20 },
        { node_id: 'NODE-002', latitude: 12, longitude: 22 },
      ]);

      assert.equal(badge.textContent, '2 NODES');
      const val = leftPanel.element.querySelector('#ce-nodes-connected-val');
      assert.equal(val.textContent, '2');

      leftPanel.destroy();
    });
  });

  describe('4. Right Intelligence Panel & Honest Placeholders', () => {
    test('renders Climate Status, Threat placeholder, and AI Agent placeholder', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      assert.ok(rightPanel.element.querySelector('#ce-card-status'), 'Status card must exist');
      assert.ok(rightPanel.element.querySelector('#ce-card-threat'), 'Threat card must exist');
      assert.ok(rightPanel.element.querySelector('#ce-card-ai-agent'), 'AI Agent card must exist');

      rightPanel.destroy();
    });

    test('threat and AI placeholders honestly report standby without fabricated intelligence', () => {
      const store = createClimateStore();
      const rightPanel = createRightPanel(store);

      const threatCard = rightPanel.element.querySelector('#ce-card-threat');
      assert.match(threatCard.textContent, /NO ACTIVE HAZARD ALERTS/);
      assert.match(threatCard.textContent, /NONE DETECTED/);

      const aiCard = rightPanel.element.querySelector('#ce-card-ai-agent');
      assert.match(aiCard.textContent, /STANDBY/);
      assert.match(aiCard.textContent, /Awaiting real-time MQTT telemetry/);

      rightPanel.destroy();
    });
  });

  describe('5. Bottom Status Bar', () => {
    test('renders realtime state, node count, telemetry connection, and API status', () => {
      const store = createClimateStore();
      const statusBar = createStatusBar(store);

      const rtText = statusBar.element.querySelector('#ce-realtime-text');
      assert.equal(rtText.textContent, REALTIME_STATES.UNAVAILABLE, 'Realtime state must default to UNAVAILABLE');

      const nodeCountText = statusBar.element.querySelector('#ce-node-count-text');
      assert.equal(nodeCountText.textContent, '0');

      const telemText = statusBar.element.querySelector('#ce-telemetry-text');
      assert.equal(telemText.textContent, 'DISCONNECTED');

      const apiText = statusBar.element.querySelector('#ce-api-text');
      assert.equal(apiText.textContent, 'UNINITIALIZED');

      statusBar.destroy();
    });

    test('realtime state pill updates to LIVE when store connection reflects LIVE', () => {
      const store = createClimateStore();
      const statusBar = createStatusBar(store);

      const rtPill = statusBar.element.querySelector('#ce-realtime-pill');
      const rtText = statusBar.element.querySelector('#ce-realtime-text');

      assert.ok(rtPill.classList.contains('unavailable'));

      store.setRealtimeState(REALTIME_STATES.LIVE);

      assert.equal(rtText.textContent, 'LIVE');
      assert.ok(rtPill.classList.contains('live'));
      assert.equal(rtPill.classList.contains('unavailable'), false);

      statusBar.destroy();
    });
  });
});

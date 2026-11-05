import { test } from 'node:test';
import assert from 'node:assert/strict';
import { displayValue, confirmsCommand } from './telemetry.js';

test('unreliable or disconnected values are never displayed as current', () => {
  const tag = { value: 750, quality: 'GOOD' };
  assert.equal(displayValue(tag, { divisor: 10 }), '75');
  assert.equal(displayValue(tag, { divisor: 10 }, false), '—');
  assert.equal(displayValue({ ...tag, quality: 'BAD' }, { divisor: 10 }), '—');
  assert.equal(displayValue({ ...tag, value: NaN }), '—');
});

test('FC06 acknowledgement alone cannot confirm the operator setpoint', () => {
  const pending = { raw: 820, previousTimestamp: 100 };
  assert.equal(confirmsCommand({ value: 820, timestamp: 100, quality: 'GOOD' }, pending), false);
  assert.equal(confirmsCommand({ value: 810, timestamp: 101, quality: 'GOOD' }, pending), false);
  assert.equal(confirmsCommand({ value: 820, timestamp: 101, quality: 'BAD' }, pending), false);
  assert.equal(confirmsCommand({ value: 820, timestamp: 101, quality: 'GOOD' }, pending), true);
});

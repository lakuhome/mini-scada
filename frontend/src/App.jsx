import { useEffect, useRef, useState } from 'react';
import useTelemetry from './useTelemetry';
import { confirmsCommand, displayValue, readJson } from './telemetry';

const time = value => value ? new Date(value * 1000).toLocaleString('ru-RU') : '—';

function History({ catalog }) {
  const [selected, setSelected] = useState('Boiler_Temp_01');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [revision, refresh] = useState(0);
  const [result, setResult] = useState({ rows: [], error: '', loading: true });
  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: '100' });
    if (start) params.set('start', String(new Date(start).getTime() / 1000));
    if (end) params.set('end', String(new Date(end).getTime() / 1000));
    // Reset the result when starting an external archive request.
    // oxlint-disable-next-line react/set-state-in-effect
    setResult({ rows: [], error: '', loading: true });
    fetch(`/api/tags/${encodeURIComponent(selected)}/history?${params}`, { signal: controller.signal })
      .then(readJson).then(data => setResult({ rows: data.history, error: '', loading: false }))
      .catch(error => { if (error.name !== 'AbortError') setResult({ rows: [], error: error.message, loading: false }); });
    return () => controller.abort();
  }, [selected, start, end, revision]);
  return <section className="panel history">
    <div className="section-heading"><h2>Архив</h2>
      <button onClick={() => refresh(value => value + 1)}>Обновить</button></div>
    <div className="filters">
      <label>Показатель<select value={selected} onChange={e => setSelected(e.target.value)}>
        {Object.entries(catalog).map(([id, meta]) => <option key={id} value={id}>{meta.title}</option>)}
      </select></label>
      <label>С <input type="datetime-local" value={start} onChange={e => setStart(e.target.value)} /></label>
      <label>По <input type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} /></label>
    </div>
    {result.error && <p role="alert" className="error">{result.error}</p>}
    <div className="table-scroll"><table><thead><tr><th>Время</th><th>Значение{catalog[selected]?.unit ? `, ${catalog[selected].unit}` : ''}</th><th>Примечание</th></tr></thead>
      <tbody>{result.rows.map((tag, index) => <tr key={`${tag.timestamp}-${index}`}><td>{time(tag.timestamp)}</td>
        <td>{displayValue(tag, catalog[selected])}</td><td className={tag.quality === 'GOOD' ? 'muted' : 'unavailable'}>{tag.quality === 'GOOD' ? '—' : 'Нет данных'}</td></tr>)}</tbody></table>
      {result.loading ? <p className="empty">Загрузка архива…</p> : !result.rows.length && !result.error && <p className="empty">За выбранный период записей нет</p>}
    </div>
  </section>;
}

function Setpoint({ meta, tag, connected }) {
  const [value, setValue] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(null);
  const [sending, setSending] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (connected && confirmsCommand(tag, pending)) {
      // Incoming PLC telemetry completes a previously submitted command.
      // oxlint-disable-next-line react/set-state-in-effect
      setPending(null);
      setMessage('Уставка применена.');
    }
  }, [tag, pending, connected]);
  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => {
      setPending(null);
      setMessage('Не удалось подтвердить изменение уставки.');
    }, 10000);
    return () => clearTimeout(timer);
  }, [pending]);
  async function submit(event) {
    event.preventDefault();
    setSending(true);
    setMessage('Отправка…');
    const raw = Math.round(Number(value) * meta.divisor);
    try {
      const acknowledgement = await readJson(await fetch('/api/tags/Temp_Setpoint_01/setpoint', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: Number(value) }),
      }));
      if (mounted.current) {
        setPending({ raw, previousTimestamp: acknowledgement.acknowledged_at });
        setMessage('Ожидание подтверждения…');
      }
    } catch (error) { if (mounted.current) setMessage(`Ошибка: ${error.message}`); }
    finally { if (mounted.current) setSending(false); }
  }
  return <section className="panel control"><h2>Температурная уставка</h2>
    <div className="current-setpoint"><span>Задано</span><strong>{displayValue(tag, meta, connected)} <small>°C</small></strong></div>
    {meta?.writable ? <form onSubmit={submit}>
      <label>Новое значение, °C<input aria-label="Новая уставка" type="number" step={1 / meta.divisor} min={meta.min} max={meta.max}
        required value={value} onChange={e => setValue(e.target.value)} placeholder={`${meta.min}–${meta.max}`} /></label>
      <p className="input-hint">{meta.min}–{meta.max} °C</p>
      <button className="primary" disabled={!connected || tag?.quality !== 'GOOD' || sending || Boolean(pending)}>Применить</button>
    </form> : <p className="muted">Изменение уставки недоступно.</p>}
    <p role="status" className="command-message">{message}</p>
  </section>;
}

export default function App() {
  const { tags, connected, receivedAt } = useTelemetry();
  const [catalog, setCatalog] = useState({});
  const [catalogError, setCatalogError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/catalog', { signal: controller.signal }).then(readJson).then(data => { setCatalog(data); setCatalogError(''); })
      .catch(error => { if (error.name !== 'AbortError') setCatalogError(error.message); });
    return () => controller.abort();
  }, [retry]);
  const plcGood = connected && Object.keys(catalog).length > 0 && Object.keys(catalog).every(id => tags[id]?.quality === 'GOOD');
  return <div className="app">
    <main><header className="page-heading"><h1>Котельная</h1>
      {connected && receivedAt && <span className="updated">Обновлено {new Date(receivedAt).toLocaleTimeString('ru-RU')}</span>}</header>
      {!connected && <p role="alert" className="notice">Нет связи с сервером.</p>}
      {connected && !plcGood && Object.keys(catalog).length > 0 && <p role="alert" className="notice">{Object.values(tags).some(tag => tag.quality === 'GOOD') ? 'Часть показаний недоступна.' : 'Показания контроллера недоступны.'}</p>}
      {catalogError && <p role="alert" className="notice">Не удалось загрузить параметры. <button onClick={() => setRetry(x => x + 1)}>Повторить</button></p>}
      <div className="workspace"><div className="readings">
        {Object.entries(catalog).filter(([id]) => id !== 'Temp_Setpoint_01').map(([id, meta]) => {
          const tag = tags[id];
          const good = connected && tag?.quality === 'GOOD';
          const value = id === 'Pump_01_Status' && good ? (tag.value ? 'Работает' : 'Остановлен') :
            id === 'Alarm_Code_01' && good ? (tag.value === 0 ? 'Нет аварий' : `Код ${tag.value}`) : displayValue(tag, meta, connected);
          const alarm = good && id === 'Alarm_Code_01' && tag.value !== 0;
          return <article className={`panel reading ${alarm ? 'alarm' : ''}`} key={id}>
            <h2>{id === 'Alarm_Code_01' ? 'Аварии' : meta.title}</h2>
            <div className="reading-value" data-testid={id}>{value}<small>{meta.unit}</small></div>
            {!good && <span className="unavailable">Нет данных</span>}
          </article>;
        })}
      </div><Setpoint meta={catalog.Temp_Setpoint_01} tag={tags.Temp_Setpoint_01} connected={connected} /></div>
      <History catalog={catalog} />
    </main>
  </div>;
}

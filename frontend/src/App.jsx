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
    <div className="section-heading"><div><span className="eyebrow">АРХИВ</span><h2>История измерений</h2></div>
      <button onClick={() => refresh(value => value + 1)}>Обновить</button></div>
    <div className="filters">
      <label>Показатель<select value={selected} onChange={e => setSelected(e.target.value)}>
        {Object.entries(catalog).map(([id, meta]) => <option key={id} value={id}>{meta.title}</option>)}
      </select></label>
      <label>С <input type="datetime-local" value={start} onChange={e => setStart(e.target.value)} /></label>
      <label>По <input type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} /></label>
    </div>
    <p className="muted">Последние 100 записей выбранного периода, от новых к старым. В архив попадают значимые изменения и смена качества.</p>
    {result.error && <p role="alert" className="error">{result.error}</p>}
    <div className="table-scroll"><table><thead><tr><th>Время</th><th>Значение, {catalog[selected]?.unit || 'ед.'}</th><th>Качество</th></tr></thead>
      <tbody>{result.rows.map((tag, index) => <tr key={`${tag.timestamp}-${index}`}><td>{time(tag.timestamp)}</td>
        <td>{displayValue(tag, catalog[selected])}</td><td><span className={`badge ${tag.quality === 'GOOD' ? 'good' : 'bad'}`}>{tag.quality}</span></td></tr>)}</tbody></table>
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
      setMessage('Уставка подтверждена повторным чтением ПЛК.');
    }
  }, [tag, pending, connected]);
  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => {
      setPending(null);
      setMessage('Подтверждение чтением не получено. Проверьте связь и текущую уставку.');
    }, 10000);
    return () => clearTimeout(timer);
  }, [pending]);
  async function submit(event) {
    event.preventDefault();
    setSending(true);
    setMessage('Отправка команды…');
    const raw = Math.round(Number(value) * meta.divisor);
    try {
      const acknowledgement = await readJson(await fetch('/api/tags/Temp_Setpoint_01/setpoint', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: Number(value) }),
      }));
      if (mounted.current) {
        setPending({ raw, previousTimestamp: acknowledgement.acknowledged_at });
        setMessage('Команда принята ПЛК. Ожидаем подтверждения чтением…');
      }
    } catch (error) { if (mounted.current) setMessage(`Ошибка: ${error.message}`); }
    finally { if (mounted.current) setSending(false); }
  }
  return <section className="panel control"><span className="eyebrow">УПРАВЛЕНИЕ</span><h2>Температурная уставка</h2>
    <p className="muted">Текущее значение</p><div className="setpoint-value">{displayValue(tag, meta, connected)} <small>°C</small></div>
    {meta?.writable ? <form onSubmit={submit}>
      <label>Новое значение, °C<input aria-label="Новая уставка" type="number" step={1 / meta.divisor} min={meta.min} max={meta.max}
        required value={value} onChange={e => setValue(e.target.value)} placeholder={`${meta.min}–${meta.max}`} /></label>
      <p className="muted">Допустимо от {meta.min} до {meta.max} °C</p>
      <button className="primary" disabled={!connected || tag?.quality !== 'GOOD' || sending || Boolean(pending)}>Применить уставку</button>
    </form> : <p className="muted">Запись не разрешена конфигурацией сервера.</p>}
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
    <header className="topbar"><a className="brand" href="/">mini<span>scada</span><small>ОПЕРАТОРСКАЯ ПАНЕЛЬ</small></a>
      <div className="connections"><span className={`badge ${connected ? 'good' : 'bad'}`}>Сервер: {connected ? 'на связи' : 'нет связи'}</span>
        <span className={`badge ${plcGood ? 'good' : 'bad'}`}>ПЛК: {plcGood ? 'данные достоверны' : 'нет достоверных данных'}</span></div></header>
    <main><div className="page-heading"><div><span className="eyebrow">ОБЪЕКТ 01 / ТЕПЛОСНАБЖЕНИЕ</span><h1>Котельная</h1><p className="muted">Мониторинг, управление и архив технологических параметров</p></div>
      <div className="updated">Последний пакет<br /><strong>{receivedAt ? new Date(receivedAt).toLocaleTimeString('ru-RU') : 'Ожидание данных'}</strong></div></div>
      {!connected && <p role="alert" className="notice">Нет связи с сервером. Значения недоступны, управление приостановлено. Переподключение выполняется автоматически.</p>}
      {connected && !plcGood && <p role="alert" className="notice">Нет достоверных показаний ПЛК. Последние значения не считаются актуальными.</p>}
      {catalogError && <p role="alert" className="notice">Не удалось загрузить описание тегов: {catalogError} <button onClick={() => setRetry(x => x + 1)}>Повторить</button></p>}
      <div className="workspace"><div className="readings">
        {Object.entries(catalog).filter(([id]) => id !== 'Temp_Setpoint_01').map(([id, meta]) => {
          const tag = tags[id];
          const good = connected && tag?.quality === 'GOOD';
          const value = id === 'Pump_01_Status' && good ? (tag.value ? 'Работает' : 'Остановлен') :
            id === 'Alarm_Code_01' && good && tag.value === 0 ? 'Нет аварий' : displayValue(tag, meta, connected);
          const alarm = good && id === 'Alarm_Code_01' && tag.value !== 0;
          return <article className={`panel reading ${!good || alarm ? 'attention' : ''}`} key={id}>
            <div className="reading-title"><h2>{meta.title}</h2><span className={`dot ${good && !alarm ? 'good' : 'bad'}`} /></div>
            <div className="reading-value" data-testid={id}>{value}<small>{meta.unit}</small></div>
            <div className="reading-footer"><span>{good ? (alarm ? 'Авария' : 'GOOD') : connected ? 'BAD' : 'Нет связи'}</span><time>{time(tag?.timestamp)}</time></div>
          </article>;
        })}
      </div><Setpoint meta={catalog.Temp_Setpoint_01} tag={tags.Temp_Setpoint_01} connected={connected} /></div>
      <History catalog={catalog} />
    </main><footer>mini-scada · Учебный стенд котельной <span>Modbus TCP / SQLite</span></footer>
  </div>;
}

export default async function teardown() {
  try {
    await fetch('http://127.0.0.1:18000/__test/shutdown', { method: 'POST' });
    // Give the fixture time to drain the archive and close its own process on Windows.
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 100));
      try { await fetch('http://127.0.0.1:18000/api/health'); }
      catch { return; }
    }
  } catch { /* The fixture may already have stopped after a startup failure. */ }
}

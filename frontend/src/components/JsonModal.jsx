import React, { useState, useEffect } from 'react';
import { X, Copy, Check, Download, Upload, AlertCircle, FileCode } from 'lucide-react';

export default function JsonModal({
  isOpen,
  onClose,
  mode = 'export', // 'export' | 'import'
  schema,
  onImportSchema,
}) {
  const [copied, setCopied] = useState(false);
  const [importText, setImportText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (mode === 'import') {
      setImportText('');
      setError('');
    }
    setCopied(false);
  }, [isOpen, mode]);

  if (!isOpen) return null;

  const jsonString = JSON.stringify(schema, null, 2);

  // Копирование в буфер
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Не удалось скопировать в буфер');
    }
  };

  // Скачивание файла config.json
  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${schema.title ? schema.title.toLowerCase().replace(/\s+/g, '_') : 'scada_config'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Импорт схемы из текста
  const handleApplyImport = () => {
    try {
      setError('');
      const parsed = JSON.parse(importText);
      if (!parsed || !Array.isArray(parsed.widgets)) {
        throw new Error('JSON должен содержать корневой массив "widgets"');
      }
      onImportSchema(parsed);
      onClose();
    } catch (e) {
      setError(`Ошибка валидации JSON: ${e.message}`);
    }
  };

  // Загрузка файла с диска
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setImportText(event.target?.result || '');
      setError('');
    };
    reader.readAsText(file);
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Заголовок модального окна */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-600/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
              <FileCode className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                {mode === 'export' ? 'Экспорт конфигурации мнемосхемы' : 'Импорт конфигурации мнемосхемы'}
              </h3>
              <p className="text-[11px] text-slate-400">
                {mode === 'export'
                  ? 'Спецификация config.json для загрузки в mini-scada'
                  : 'Вставьте готовый JSON или загрузите файл с диска'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Тело модального окна */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 select-text">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {mode === 'export' ? (
            <div className="relative">
              <pre className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs font-mono text-cyan-300 overflow-x-auto max-h-[50vh]">
                {jsonString}
              </pre>
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder='Вставьте сюда JSON-код схемы (например: { "widgets": [...] })'
                className="w-full h-72 bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 resize-none"
              />

              <div className="flex items-center justify-between text-xs text-slate-400">
                <label className="flex items-center gap-1.5 cursor-pointer hover:text-cyan-400 transition-colors">
                  <Upload className="w-3.5 h-3.5" />
                  <span>Загрузить .json файл</span>
                  <input
                    type="file"
                    accept=".json"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
                <span className="text-[11px] text-slate-500">
                  Формат должен соответствовать docs/schema_designer_spec.md
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Футер с кнопками действий */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-end gap-2.5 bg-slate-950/40 select-none">
          {mode === 'export' ? (
            <>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Скопировано!' : 'Копировать JSON'}</span>
              </button>

              <button
                onClick={handleDownload}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-950 transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Скачать config.json</span>
              </button>
            </>
          ) : (
            <>
              <button
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleApplyImport}
                disabled={!importText.trim()}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-md shadow-cyan-950 transition-all"
              >
                <span>Применить схему</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

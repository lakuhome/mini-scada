import React, { useState, useEffect, useCallback } from 'react';
import Toolbar from './components/Toolbar';
import SidebarPalette from './components/SidebarPalette';
import Canvas from './components/Canvas';
import PropertiesPanel from './components/PropertiesPanel';
import JsonModal from './components/JsonModal';
import { 
  EQUIPMENT_TYPES, 
  INITIAL_DEMO_SCHEMA 
} from './constants/equipmentCatalog';

export default function App() {
  const [schema, setSchema] = useState(() => {
    const saved = localStorage.getItem('mini_scada_schema_draft');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        // fallback
      }
    }
    return INITIAL_DEMO_SCHEMA;
  });

  const [selectedId, setSelectedId] = useState(null);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [modal, setModal] = useState({ isOpen: false, mode: 'export' });

  // Автосохранение черновика в LocalStorage
  useEffect(() => {
    localStorage.setItem('mini_scada_schema_draft', JSON.stringify(schema));
  }, [schema]);

  const selectedWidget = schema.widgets.find((w) => w.id === selectedId) || null;

  // Добавление виджета по типу
  const handleAddWidget = useCallback((type) => {
    const meta = EQUIPMENT_TYPES[type];
    if (!meta) return;

    const count = schema.widgets.filter((w) => w.type === type).length + 1;
    const newId = `${type}_${String(count).padStart(2, '0')}`;

    // Размещение ближе к центру или со смещением
    const newWidget = {
      id: newId,
      type: type,
      title: `${meta.title} #${count}`,
      x: 100 + (schema.widgets.length % 5) * 40,
      y: 100 + (schema.widgets.length % 5) * 40,
      tag_id: meta.defaultTag || null,
      tag_setpoint: meta.defaultSetpoint || null,
      unit: meta.defaultUnit || '',
      min_val: meta.defaultMin ?? null,
      max_val: meta.defaultMax ?? null,
    };

    setSchema((prev) => ({
      ...prev,
      widgets: [...prev.widgets, newWidget],
    }));
    setSelectedId(newId);
  }, [schema.widgets]);

  // Добавление виджета по конкретным координатам (Drop)
  const handleAddWidgetAt = useCallback((type, x, y) => {
    const meta = EQUIPMENT_TYPES[type];
    if (!meta) return;

    const count = schema.widgets.filter((w) => w.type === type).length + 1;
    const newId = `${type}_${String(count).padStart(2, '0')}`;

    const newWidget = {
      id: newId,
      type: type,
      title: `${meta.title} #${count}`,
      x,
      y,
      tag_id: meta.defaultTag || null,
      tag_setpoint: meta.defaultSetpoint || null,
      unit: meta.defaultUnit || '',
      min_val: meta.defaultMin ?? null,
      max_val: meta.defaultMax ?? null,
    };

    setSchema((prev) => ({
      ...prev,
      widgets: [...prev.widgets, newWidget],
    }));
    setSelectedId(newId);
  }, [schema.widgets]);

  // Перемещение виджета
  const handleMoveWidget = useCallback((id, x, y) => {
    setSchema((prev) => ({
      ...prev,
      widgets: prev.widgets.map((w) => (w.id === id ? { ...w, x, y } : w)),
    }));
  }, []);

  // Обновление свойств активного виджета
  const handleUpdateWidget = useCallback((patch) => {
    if (!selectedId) return;
    setSchema((prev) => ({
      ...prev,
      widgets: prev.widgets.map((w) => (w.id === selectedId ? { ...w, ...patch } : w)),
    }));
  }, [selectedId]);

  // Удаление виджета
  const handleDeleteWidget = useCallback((id) => {
    setSchema((prev) => ({
      ...prev,
      widgets: prev.widgets.filter((w) => w.id !== id),
    }));
    setSelectedId(null);
  }, []);

  // Дублирование виджета
  const handleDuplicateWidget = useCallback((id) => {
    const target = schema.widgets.find((w) => w.id === id);
    if (!target) return;

    const newId = `${target.type}_${Date.now().toString().slice(-4)}`;
    const cloned = {
      ...target,
      id: newId,
      title: `${target.title} (копия)`,
      x: target.x + 20,
      y: target.y + 20,
    };

    setSchema((prev) => ({
      ...prev,
      widgets: [...prev.widgets, cloned],
    }));
    setSelectedId(newId);
  }, [schema.widgets]);

  // Очистка схемы
  const handleClear = useCallback(() => {
    if (window.confirm('Вы уверены, что хотите удалить все элементы со схемы?')) {
      setSchema((prev) => ({ ...prev, widgets: [] }));
      setSelectedId(null);
    }
  }, []);

  // Сброс к демо-схеме
  const handleResetDemo = useCallback(() => {
    if (window.confirm('Загрузить типовую схему котельной? Текущие несохраненные изменения будут заменены.')) {
      setSchema(INITIAL_DEMO_SCHEMA);
      setSelectedId(null);
    }
  }, []);

  // Клавиатурные сокращения (Delete, стрелки)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Игнорируем, если фокус в инпуте
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        handleDeleteWidget(selectedId);
      } else if (selectedId && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
        const step = snapToGrid ? (schema.grid?.cell_size || 20) : 5;
        const target = schema.widgets.find((w) => w.id === selectedId);
        if (!target) return;

        let dx = 0;
        let dy = 0;
        if (e.key === 'ArrowUp') dy = -step;
        if (e.key === 'ArrowDown') dy = step;
        if (e.key === 'ArrowLeft') dx = -step;
        if (e.key === 'ArrowRight') dx = step;

        handleMoveWidget(selectedId, Math.max(0, target.x + dx), Math.max(0, target.y + dy));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedId, snapToGrid, schema, handleDeleteWidget, handleMoveWidget]);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100 antialiased">
      {/* Верхний тулбар */}
      <Toolbar
        title={schema.title}
        setTitle={(title) => setSchema((prev) => ({ ...prev, title }))}
        snapToGrid={snapToGrid}
        setSnapToGrid={setSnapToGrid}
        onResetDemo={handleResetDemo}
        onClear={handleClear}
        onOpenExport={() => setModal({ isOpen: true, mode: 'export' })}
        onOpenImport={() => setModal({ isOpen: true, mode: 'import' })}
        widgetCount={schema.widgets.length}
      />

      {/* Основная рабочая область (Палитра | Холст | Свойства) */}
      <div className="flex flex-1 overflow-hidden">
        <SidebarPalette onAddWidget={handleAddWidget} />

        <Canvas
          schema={schema}
          selectedId={selectedId}
          onSelectWidget={setSelectedId}
          onMoveWidget={handleMoveWidget}
          onAddWidgetAt={handleAddWidgetAt}
          snapToGrid={snapToGrid}
        />

        <PropertiesPanel
          selectedWidget={selectedWidget}
          onUpdateWidget={handleUpdateWidget}
          onDeleteWidget={handleDeleteWidget}
          onDuplicateWidget={handleDuplicateWidget}
        />
      </div>

      {/* Модальное окно Экспорта / Импорта */}
      <JsonModal
        isOpen={modal.isOpen}
        mode={modal.mode}
        schema={schema}
        onClose={() => setModal({ isOpen: false, mode: 'export' })}
        onImportSchema={(newSchema) => {
          setSchema(newSchema);
          setSelectedId(null);
        }}
      />
    </div>
  );
}

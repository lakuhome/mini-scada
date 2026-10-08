import React, { useRef, useState, useEffect } from 'react';
import GostIcon from './GostIcon';
import { EQUIPMENT_TYPES } from '../constants/equipmentCatalog';

export default function Canvas({
  schema,
  selectedId,
  onSelectWidget,
  onMoveWidget,
  onAddWidgetAt,
  snapToGrid,
}) {
  const containerRef = useRef(null);
  const [draggingId, setDraggingId] = useState(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const { width = 1200, height = 700, cell_size = 20 } = schema.grid || {};

  // Обработка начала перетаскивания элемента
  const handleWidgetMouseDown = (e, widget) => {
    e.stopPropagation();
    onSelectWidget(widget.id);

    const canvasRect = containerRef.current.getBoundingClientRect();
    setDraggingId(widget.id);
    setDragOffset({
      x: e.clientX - canvasRect.left - widget.x,
      y: e.clientY - canvasRect.top - widget.y,
    });
  };

  // Перемещение мыши по холсту
  const handleMouseMove = (e) => {
    if (!draggingId) return;

    const canvasRect = containerRef.current.getBoundingClientRect();
    let newX = e.clientX - canvasRect.left - dragOffset.x;
    let newY = e.clientY - canvasRect.top - dragOffset.y;

    // Ограничение границами холста
    newX = Math.max(0, Math.min(newX, width - 80));
    newY = Math.max(0, Math.min(newY, height - 60));

    // Привязка к сетке
    if (snapToGrid) {
      newX = Math.round(newX / cell_size) * cell_size;
      newY = Math.round(newY / cell_size) * cell_size;
    }

    onMoveWidget(draggingId, newX, newY);
  };

  // Окончание перетаскивания
  const handleMouseUp = () => {
    setDraggingId(null);
  };

  // Drag and drop из боковой панели
  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData('text/plain');
    if (!type || !EQUIPMENT_TYPES[type]) return;

    const canvasRect = containerRef.current.getBoundingClientRect();
    let dropX = e.clientX - canvasRect.left - 40;
    let dropY = e.clientY - canvasRect.top - 40;

    if (snapToGrid) {
      dropX = Math.round(dropX / cell_size) * cell_size;
      dropY = Math.round(dropY / cell_size) * cell_size;
    }

    onAddWidgetAt(type, Math.max(0, dropX), Math.max(0, dropY));
  };

  return (
    <div
      className="flex-1 bg-slate-950 overflow-auto p-8 relative flex items-center justify-center select-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onClick={() => onSelectWidget(null)}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Сам холст мнемосхемы */}
      <div
        ref={containerRef}
        style={{
          width: `${width}px`,
          height: `${height}px`,
          backgroundImage: `
            linear-gradient(to right, rgba(51, 65, 85, 0.25) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(51, 65, 85, 0.25) 1px, transparent 1px)
          `,
          backgroundSize: `${cell_size}px ${cell_size}px`,
        }}
        className="bg-slate-900/90 rounded-2xl border-2 border-slate-800 shadow-2xl relative overflow-hidden transition-all"
      >
        {/* Водяной знак схемы */}
        <div className="absolute top-4 left-5 pointer-events-none opacity-40">
          <div className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
            {schema.title || 'Мнемосхема SCADA'}
          </div>
          <div className="text-[9px] font-mono text-slate-600">
            {width} × {height} px | Сетка: {cell_size} px
          </div>
        </div>

        {/* Отрисовка всех виджетов */}
        {schema.widgets.map((widget) => {
          const isSelected = widget.id === selectedId;
          const meta = EQUIPMENT_TYPES[widget.type] || {};

          return (
            <div
              key={widget.id}
              style={{
                left: `${widget.x}px`,
                top: `${widget.y}px`,
              }}
              onMouseDown={(e) => handleWidgetMouseDown(e, widget)}
              className={`absolute cursor-move transition-shadow rounded-xl p-2.5 flex flex-col items-center justify-center border group ${
                isSelected
                  ? 'bg-slate-800/95 border-cyan-400 shadow-xl shadow-cyan-950/60 ring-2 ring-cyan-500/30 z-10'
                  : 'bg-slate-900/80 hover:bg-slate-800/80 border-slate-700/80 hover:border-slate-600 z-0'
              }`}
            >
              {/* Верхняя плашка с названием */}
              <div className="text-[10px] font-semibold text-slate-300 truncate max-w-[120px] mb-1.5 text-center pointer-events-none">
                {widget.title}
              </div>

              {/* Иконка оборудования по ГОСТ */}
              <div className="w-14 h-14 flex items-center justify-center p-1 pointer-events-none">
                <GostIcon
                  type={widget.type}
                  className={`w-full h-full transition-colors ${
                    isSelected ? 'text-cyan-300' : 'text-cyan-400'
                  }`}
                  active={isSelected}
                />
              </div>

              {/* Нижняя плашка: привязанный тег или уставка */}
              <div className="mt-1 flex flex-col items-center gap-0.5 pointer-events-none">
                {widget.tag_id ? (
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300/90 border border-slate-800 truncate max-w-[110px]">
                    {widget.tag_id}
                  </span>
                ) : (
                  <span className="text-[9px] font-mono text-slate-500 italic">
                    нет тега
                  </span>
                )}

                {widget.unit && (
                  <span className="text-[8px] text-slate-400 font-mono">
                    [{widget.unit}]
                  </span>
                )}
              </div>

              {/* Маркер выделения угловой */}
              {isSelected && (
                <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-cyan-400 rounded-full border border-slate-900" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

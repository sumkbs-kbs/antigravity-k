/**
 * SplitPane — Resizable panel layout using Split.js
 * ===================================================
 * A React wrapper around Split.js that provides draggable panel dividers.
 * Supports horizontal (col-resize) and vertical (row-resize) layouts.
 * Persists panel sizes to localStorage.
 * Re-layouts Monaco Editor and xterm when drag completes.
 */
// @ts-nocheck


import React, { useRef, useEffect, useCallback, useState } from 'react';
import Split from 'split.js';

export interface SplitPaneProps {
  /** Panel elements as children (2-4 panels recommended) */
  children: React.ReactNode;
  /** Layout direction */
  direction?: 'horizontal' | 'vertical';
  /** Initial sizes as percentages (e.g. [20, 50, 30]) */
  initialSizes?: number[];
  /** Minimum panel sizes in pixels */
  minSizes?: number[];
  /** Storage key for persisting sizes in localStorage */
  storageKey?: string;
  /** Gutter size in pixels */
  gutterSize?: number;
  /** Callback when drag ends with new sizes */
  onDragEnd?: (sizes: number[]) => void;
  /** Additional className */
  className?: string;
}

const SplitPane: React.FC<SplitPaneProps> = ({
  children,
  direction = 'horizontal',
  initialSizes,
  minSizes,
  storageKey,
  gutterSize = 6,
  onDragEnd,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const splitRef = useRef<Split.Instance | null>(null);

  // Build children array for Split.js
  const childArray = React.Children.toArray(children).filter(Boolean);

  // Initialize Split.js
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const panelElements: HTMLElement[] = [];
    container.querySelectorAll<HTMLElement>('.split-panel').forEach(el => {
      panelElements.push(el);
    });

    if (panelElements.length < 2) return;

    // Determine sizes: localStorage > prop > equal distribution
    const count = panelElements.length;
    let sizes = (initialSizes && initialSizes.length === count)
      ? initialSizes
      : count === 3 ? [20, 45, 35] : Array(count).fill(100 / count);

    if (storageKey) {
      try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
          const parsed = JSON.parse(stored) as number[];
          if (Array.isArray(parsed) && parsed.length === count) {
            sizes = parsed;
          }
        }
      } catch { /* ignore */ }
    }

    const isHorizontal = direction === 'horizontal';

    try {
      splitRef.current = Split(panelElements, {
        sizes,
        minSize: minSizes || (isHorizontal ? [180, 200, 240] : [100]),
        gutterSize,
        direction: isHorizontal ? 'horizontal' : 'vertical',
        cursor: isHorizontal ? 'col-resize' : 'row-resize',
        onDragEnd: () => {
          if (!splitRef.current) return;
          const newSizes = splitRef.current.getSizes();

          // Persist to localStorage
          if (storageKey) {
            localStorage.setItem(storageKey, JSON.stringify(newSizes));
          }

          // Trigger window resize for Monaco Editor / xterm to re-layout
          window.dispatchEvent(new Event('resize'));

          onDragEnd?.(newSizes);
        },
      });
    } catch (err) {
      console.error('[SplitPane] Failed to initialize Split.js:', err);
    }

    return () => {
      splitRef.current?.destroy();
      splitRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childArray.length, direction, gutterSize, minSizes, storageKey, onDragEnd]);

  return (
    <div
      ref={containerRef}
      className={`split-pane-container ${direction} ${className}`}
      style={{
        display: 'flex',
        flexDirection: direction === 'horizontal' ? 'row' : 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {childArray.map((child, index) => (
        <div
          key={index}
          className="split-panel"
          style={{
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
          }}
        >
          {child}
        </div>
      ))}
    </div>
  );
};

export default SplitPane;

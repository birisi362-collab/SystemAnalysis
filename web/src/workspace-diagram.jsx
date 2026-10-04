import React, { useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  useNodesState,
  useReactFlow,
  useUpdateNodeInternals,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import {
  Layers3,
  Plus,
  Link2,
  Maximize,
  LayoutGrid,
  MessageSquare,
  Eye,
  EyeOff,
} from "lucide-react";
import { Button, cats, types } from "./workspace-ui.jsx";
import { connectionLanes, connectionPorts } from "./connection-routing.js";
import { ArchitectureEdge } from "./workspace-edge.jsx";

function ComponentNode({ id, data, selected }) {
  const update = useUpdateNodeInternals();
  const portKey = (data.ports || [])
    .map((p) => `${p.id}:${p.side}:${p.percent}`)
    .join("|");
  useEffect(() => {
    const frame = requestAnimationFrame(() => update(id));
    return () => cancelAnimationFrame(frame);
  }, [id, portKey, update]);
  const sideCount = Math.max(
    0,
    ...["left", "right"].map(
      (side) => (data.ports || []).filter((p) => p.side === side).length,
    ),
  );
  return (
    <div
      className={`arch-node ${selected ? "selected" : ""} ${data.dim ? "dim" : ""} ${data.highlight ? "highlight" : ""} ${data.category === "external" ? "external" : ""} preview-${data._preview || "none"}`}
      style={{ minHeight: Math.max(106, sideCount * 32 + 20) }}
    >
      {(data.ports || []).map((p) => (
        <Handle
          key={p.id}
          id={p.id}
          type={p.kind}
          isConnectable={false}
          position={Position[p.side[0].toUpperCase() + p.side.slice(1)]}
          style={{
            ...(p.side === "top" || p.side === "bottom"
              ? { left: p.percent + "%" }
              : { top: p.percent + "%" }),
            opacity: 0,
            pointerEvents: "none",
          }}
        />
      ))}
      {["top", "bottom", "left", "right"].map((side) => (
        <React.Fragment key={side}>
          <Handle
            type="target"
            id={"target-" + side}
            position={Position[side[0].toUpperCase() + side.slice(1)]}
            style={
              side === "top" || side === "bottom"
                ? { left: "46%" }
                : { top: "46%" }
            }
          />
          <Handle
            type="source"
            id={"source-" + side}
            position={Position[side[0].toUpperCase() + side.slice(1)]}
            style={
              side === "top" || side === "bottom"
                ? { left: "54%" }
                : { top: "54%" }
            }
          />
        </React.Fragment>
      ))}
      <div className="node-top">
        <span className="node-icon">
          <Layers3 size={15} />
        </span>
        <span>{cats[data.category] || "Bileşen"}</span>
        {data._preview && (
          <span className="preview-label">
            {data._preview === "remove" ? "Kaldırılacak" : "Önizleme"}
          </span>
        )}
      </div>
      <strong>{data.name || "Yeni bileşen"}</strong>
      <div className="node-meta">
        <span>
          {data.evidence?.length
            ? `${data.evidence.length} kaynak`
            : data.engineer
              ? "Mühendis eklemesi"
              : "Belge taslağı"}
        </span>
        {data.findingCount > 0 && (
          <button
            className="nodrag finding-dot"
            aria-label={`${data.name} önerilerini göster`}
            onClick={(e) => {
              e.stopPropagation();
              data.onFinding();
            }}
          >
            <MessageSquare size={12} />
            {data.findingCount}
          </button>
        )}
      </div>
    </div>
  );
}
const nodeTypes = { architecture: ComponentNode };
const edgeTypes = { architecture: ArchitectureEdge };
export function layout(a) {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setGraph({
    rankdir: "TB",
    nodesep: 65,
    ranksep: 75,
    marginx: 30,
    marginy: 30,
  });
  g.setDefaultEdgeLabel(() => ({}));
  a.components.forEach((c) => g.setNode(c.id, { width: 210, height: 106 }));
  a.connections.forEach((e) => {
    if (g.hasNode(e.source) && g.hasNode(e.target))
      g.setEdge(e.source, e.target, {}, e.id);
  });
  dagre.layout(g);
  return Object.fromEntries(
    a.components.map((c) => [
      c.id,
      { x: g.node(c.id).x - 105, y: g.node(c.id).y - 53 },
    ]),
  );
}

export function WorkspaceDiagram({
  project,
  architecture,
  selection,
  focus,
  focusKey,
  onSelect,
  onFinding,
  onNew,
  commit,
  busy,
  preview,
  markers,
  onMarkers,
}) {
  const rf = useReactFlow(),
    positions = useRef({}),
    initial = useRef(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const auto = useMemo(() => layout(architecture), [architecture]);
  const focused = new Set(focus || []);
  architecture.connections
    .filter((e) => focused.has(e.id))
    .forEach((e) => {
      focused.add(e.source);
      focused.add(e.target);
    });
  const topics = project.topics.filter((t) => t.status !== "completed");
  useEffect(() => {
    const saved = project.state.positions;
    setNodes((old) =>
      architecture.components.map((c) => ({
        id: c.id,
        type: "architecture",
        position:
          saved[c.id] ||
          positions.current[c.id] ||
          old.find((n) => n.id === c.id)?.position ||
          auto[c.id],
        data: c,
      })),
    );
  }, [architecture, project.state.positions]);
  useEffect(() => {
    if (initial.current && nodes.length) {
      initial.current = false;
      requestAnimationFrame(() => rf.fitView({ padding: 0.2, maxZoom: 1 }));
    }
  }, [nodes.length]);
  useEffect(() => {
    if (!focusKey || !focused.size) return;
    const ids = architecture.components
      .filter((c) => focused.has(c.id))
      .map((c) => ({ id: c.id }));
    if (ids.length)
      requestAnimationFrame(() =>
        rf.fitView({ nodes: ids, padding: 0.55, maxZoom: 1.1, duration: 250 }),
      );
  }, [focusKey]);
  const lanes = connectionLanes(architecture.connections);
  const ports = connectionPorts(nodes, architecture.connections, lanes);
  const shown = nodes.map((n) => {
    const findings = topics.filter((t) => t.object_ids.includes(n.id));
    return {
      ...n,
      selected: selection?.kind === "component" && selection.id === n.id,
      data: {
        ...n.data,
        ports: ports.byNode.get(n.id),
        highlight: focused.has(n.id),
        dim: focused.size > 0 && !focused.has(n.id),
        engineer: !!project.state.provenance["component:" + n.id],
        findingCount: markers ? findings.length : 0,
        onFinding: () => onFinding(findings[0]?.id),
      },
    };
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = architecture.connections
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => {
      const selected =
          selection?.kind === "connection" && selection.id === e.id,
        highlight = focused.has(e.id),
        sameFocusedPair = focused.has(e.source) && focused.has(e.target),
        color =
          e._preview === "remove"
            ? "#c96955"
            : e._preview
              ? "#98772d"
              : selected || highlight
                ? "#087f8c"
                : e.type === "power"
                  ? "#bc8640"
                  : "#768b9c";
      return {
        ...e,
        type: "architecture",
        ...ports.byEdge.get(e.id),
        data: {
          lane: { ...lanes.get(e.id), separatedPorts: true },
          bidirectional: e.direction === "bidirectional",
          description: `${architecture.components.find((c) => c.id === e.source)?.name} ${e.direction === "bidirectional" ? "↔" : "→"} ${architecture.components.find((c) => c.id === e.target)?.name}: ${e.protocol || e.label || types[e.type]}`,
          onSelect: (id) => onSelect({ kind: "connection", id }),
        },
        label:
          (e._preview
            ? e._preview === "remove"
              ? "Kaldırılacak · "
              : "Önizleme · "
            : "") + (e.protocol || e.label || types[e.type]),
        selected,
        style: {
          stroke: color,
          strokeWidth: selected || highlight ? 2.5 : 1.6,
          strokeDasharray: e._preview || e.type === "power" ? "6 4" : undefined,
          opacity: focused.size && !highlight && !sameFocusedPair ? 0.28 : 1,
        },
        labelStyle: { fontSize: 12, fill: color },
        labelBgStyle: { fill: "#fff" },
        labelBgPadding: [7, 4],
        markerEnd: { type: MarkerType.ArrowClosed, color },
        markerStart:
          e.direction === "bidirectional"
            ? { type: MarkerType.ArrowClosed, color }
            : undefined,
        interactionWidth: 30,
        ariaLabel: `${architecture.components.find((c) => c.id === e.source)?.name} ${e.direction === "bidirectional" ? "↔" : "→"} ${architecture.components.find((c) => c.id === e.target)?.name}: ${e.protocol || types[e.type]}`,
      };
    });
  return (
    <section className="canvas-area studio-canvas" aria-label="Mimari şema">
      <div className="canvas-toolbar">
        <div className="toolbar-group">
          <Button
            icon={Plus}
            disabled={busy || preview}
            onClick={() => onNew("component")}
          >
            Bileşen
          </Button>
          <Button
            icon={Link2}
            disabled={busy || preview || architecture.components.length < 2}
            onClick={() => onNew("connection")}
          >
            Bağlantı
          </Button>
        </div>
        <div className="toolbar-group">
          <button
            className="icon-button"
            aria-label={
              markers ? "Bulgu işaretlerini gizle" : "Bulgu işaretlerini göster"
            }
            onClick={onMarkers}
          >
            {markers ? <Eye size={17} /> : <EyeOff size={17} />}
          </button>
          <button
            className="icon-button"
            aria-label="Otomatik yerleştir"
            disabled={busy || preview}
            onClick={() => commit("layout", "", auto)}
          >
            <LayoutGrid size={17} />
          </button>
          <button
            className="icon-button"
            aria-label="Şemayı ekrana sığdır"
            onClick={() => rf.fitView({ padding: 0.2, duration: 200 })}
          >
            <Maximize size={17} />
          </button>
        </div>
      </div>
      {preview && (
        <div className="preview-ribbon">
          Önizleme · Uyguladığınızda kaydedilecek
        </div>
      )}
      <ReactFlow
        nodes={shown}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, n) => onSelect({ kind: "component", id: n.id })}
        onEdgeClick={(_, e) => onSelect({ kind: "connection", id: e.id })}
        onConnect={(params) => onNew("connection", params)}
        onNodeDragStop={(_, n) => {
          positions.current[n.id] = n.position;
          commit("layout", "", { [n.id]: n.position });
        }}
        nodesDraggable={!busy && !preview}
        nodesConnectable={!busy && !preview}
        deleteKeyCode={null}
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color="#d6e2e5" gap={22} size={1} />
        <Controls showInteractive={false} />
        <MiniMap nodeColor="#a7bec7" maskColor="#f3f7f8bb" pannable zoomable />
      </ReactFlow>
      <div className="canvas-caption">
        <span>
          <i className="legend-line" />
          Veri / kontrol
        </span>
        <span>
          <i className="legend-line power" />
          Güç
        </span>
        <span>Bir öğeyi seçerek düzenleyin</span>
      </div>
    </section>
  );
}

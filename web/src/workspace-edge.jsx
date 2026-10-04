import React from "react";
import { BaseEdge, EdgeLabelRenderer } from "@xyflow/react";
import { routedPath } from "./connection-routing.js";

export function ArchitectureEdge(props) {
  const {
    id,
    data,
    label,
    style,
    markerStart,
    markerEnd,
    selected,
    interactionWidth,
  } = props;
  const { path, labelX, labelY, labelAnchor } = routedPath(props, data.lane);
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={style}
        markerStart={markerStart}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth}
      />
      <EdgeLabelRenderer>
        <button
          className={`connection-label nodrag nopan ${selected ? "selected" : ""}`}
          style={{
            transform: `translate(${labelX}px, ${labelY}px) translate(${labelAnchor === "left" ? "-100%" : labelAnchor === "right" ? "0%" : "-50%"}, -50%)`,
            color: style.stroke,
            opacity: style.opacity,
            maxWidth:
              data.lane.count > 2 && labelAnchor !== "center"
                ? Math.max(50, Math.min(130, 336 / data.lane.count - 8))
                : 190,
          }}
          title={data.description}
          aria-label={data.description}
          onClick={() => data.onSelect(id)}
        >
          {data.lane.count > 1 && (
            <small>
              {data.lane.index + 1}/{data.lane.count}
            </small>
          )}
          {data.bidirectional && <span aria-hidden="true">↔ </span>}
          {label}
        </button>
      </EdgeLabelRenderer>
    </>
  );
}

/**
 * Ontology Graph Viewer - Edge visibility filters
 * Used by computeEdgeStyle; neighbourhood edges are never hidden.
 */

import { HUB_EDGE_CAP } from "./utils.js";

export function shouldHideEdge(e, stateSnapshot, context) {
  const { nhopResult } = stateSnapshot;
  const inNeighbourhood = nhopResult?.edgeIds?.has(e.id) ?? false;
  if (inNeighbourhood) return false;

  const { edgeFilter, viewMode, zoomScale, showAllHubEdges } = stateSnapshot;
  const { hubIds, nodeClusterMap, nodeMap } = context;
  const rel = e.relation || "";

  let hideByFilter = false;
  if (edgeFilter === "intraCluster") {
    const fromCluster = nodeClusterMap[e.from];
    const toCluster = nodeClusterMap[e.to];
    hideByFilter =
      (fromCluster == null) !== (toCluster == null) ||
      (fromCluster != null && toCluster != null && fromCluster !== toCluster);
  } else if (edgeFilter === "subClassOf") hideByFilter = rel !== "subClassOf";
  else if (edgeFilter === "type") hideByFilter = rel !== "type" && rel !== "instanceOf";
  else if (edgeFilter === "other") hideByFilter = rel === "subClassOf" || rel === "type" || rel === "instanceOf";

  const hierarchyRels = ["subClassOf"];
  const structuralRels = ["subClassOf", "type", "instanceOf", "part_of", "contains"];
  let hideByZoom = false;
  if (zoomScale < 0.45) hideByZoom = hierarchyRels.indexOf(rel) === -1;
  else if (zoomScale < 0.75) hideByZoom = structuralRels.indexOf(rel) === -1;

  let hideByHub = false;
  if (!showAllHubEdges && hubIds) {
    if (hubIds.has(e.from) && e.hubOutRank != null && e.hubOutRank >= HUB_EDGE_CAP) hideByHub = true;
    if (hubIds.has(e.to) && e.hubInRank != null && e.hubInRank >= HUB_EDGE_CAP) hideByHub = true;
  }
  if (viewMode === "classes" && rel !== "subClassOf") return true;
  if (viewMode === "instances" && rel !== "type" && rel !== "instanceOf") return true;
  if (nodeMap && nodeMap[e.from]?.hidden) return true;
  if (nodeMap && nodeMap[e.to]?.hidden) return true;
  return hideByFilter || hideByZoom || hideByHub;
}

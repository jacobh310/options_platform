import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "./api";

export const ACTIVE = ["queued", "running"];

/** Pipeline run history. Polls while a run is active and refreshes dependent data when one finishes. */
export function useRuns() {
  const qc = useQueryClient();
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs,
    refetchInterval: (q) => (q.state.data?.some((r) => ACTIVE.includes(r.status)) ? 2000 : false),
  });

  const finishedCount = runs.data?.filter((r) => !ACTIVE.includes(r.status)).length;
  useEffect(() => {
    qc.invalidateQueries({ queryKey: ["universe"] });
    qc.invalidateQueries({ queryKey: ["signals"] });
  }, [finishedCount, qc]);

  return runs;
}

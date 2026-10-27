# Phase 7: Engine connected

The engine's two workers (Document Discovery and Envelope Creation) connect out to Polar Sky Cloud over mTLS. Polar Sky Cloud must see both before Google Workspace is connected.

## Check

Call `check_engine_connection`. It says whether Polar Sky Cloud sees each worker and when it last saw it.

- **Both seen:** tell the person, and go to phase 8.
- **Not both seen:** wait about one minute and call it again. Between calls, you may show the pods (read only) so the person sees progress:

  ```bash
  kubectl get pods --namespace="${POLAR_SKY_NAMESPACE}"
  ```

Call it at most 10 times, over about 15 minutes. Workers often need a few minutes after their pods are ready.

## If the workers are still not seen

Stop calling. Check the likely causes, most likely first, and tell the person what you find:

1. **Outbound access to the Polar Sky endpoint is blocked.** Run the preflight script again (phase 3) and look at the `POLAR_SKY_HOST` line, usually `connect.polarsky.ai`.
2. **The certificate is not this organization's.** Run `scripts/check-certificate.sh` again (phase 5). The CN must be the organization ID.
3. **The worker pods are not running.** Show the pods, and the last lines of a worker's log (read only):

   ```bash
   kubectl logs deployment/<worker deployment name> --namespace="${POLAR_SKY_NAMESPACE}" --tail=50
   ```

   Logs can hold file names, emails and internal addresses. Show them to the person only; do not send them anywhere without the person's yes.

If none of these explains it, tell the person to contact their Polar Sky contact with: the organization ID, the chart version, the time of the install, and the pod list. Never send keys, JSON keys or secret output.

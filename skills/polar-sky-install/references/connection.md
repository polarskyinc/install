# Phase 7: Engine connected

**Tell the person:** Polar Sky checks that the engine has reached Polar Sky Cloud. It usually takes a few minutes, and you check it for the person.

The engine's two workers (Document Discovery and Envelope Creation) connect out to Polar Sky Cloud over mTLS. Polar Sky Cloud must see both before Google Workspace or Microsoft 365 is connected.

## Check

Call `check_engine_connection`. It says whether Polar Sky Cloud sees each worker and when it last saw it.

- **Both seen:** tell the person. For Microsoft 365, first do [Microsoft 365: the engine app in the workers](#microsoft-365-the-engine-app-in-the-workers) below, then go to phase 9. For Google Workspace, go to phase 8 when the plan has the Okta stage and it is not done yet, otherwise to phase 9. Both seen means the workers reach Polar Sky Cloud. It does not mean the AI models run: if phase 6 found a model pod not ready, say that too.
- **Not both seen:** wait about one minute and call it again. Between calls, you may show the pods (read only) so the person sees progress:

  ```bash
  kubectl get pods --namespace="${POLAR_SKY_NAMESPACE}"
  ```

Call it at most 10 times, over about 15 minutes. Workers often need a few minutes after their pods are ready. Tell the person you are waiting for the engine to reach Polar Sky Cloud, and report each check in one line.

## Microsoft 365: the engine app in the workers

Only for Microsoft 365, once both workers are seen.

1. **The time the engine could first connect** is in `values.env` as `POLAR_SKY_ENGINE_CONNECTED_AT`, written right before the chart install ([Engine install](engine.md#install-the-polar-sky-chart)). Every `get_install_values` call for Microsoft 365 passes it as `reading_since`. If it is missing, for example because the engine was installed in another way, record the time now, with the command in that section, and write it the same way. Files the engine read before it then do not count, so reading may show as not confirmed for longer, but files an earlier engine read can never count.

2. **Check that both workers started with the engine app** (read only). Each command prints only a count of matching log lines, never the lines themselves:

   ```bash
   kubectl logs deployment/polar-sky-document-discovery --namespace="${POLAR_SKY_NAMESPACE}" | grep -c 'MS365 discoverer registered'
   ```

   ```bash
   kubectl logs deployment/polar-sky-envelope-creation --namespace="${POLAR_SKY_NAMESPACE}" | grep -c 'MS365 creator registered'
   ```

   Each must print 1 or more. This shows that both workers found all three values of the secret; whether the values are right shows only when Polar Sky reads the first files through the engine ([Connect Microsoft 365](microsoft365.md#confirm-polar-sky-started-reading)). A `0` means that worker started without the engine app, and Microsoft 365 is off in it: the secret misses one of its three values, or the chart was installed without the Microsoft 365 values. See what the secret holds; this shows only its key names and sizes, never the values:

   ```bash
   kubectl describe secret microsoft365-credentials --namespace="${POLAR_SKY_NAMESPACE}"
   ```

   It must list `client-id`, `tenant-id` and `certificate-base64`, none of them with 0 bytes. Tell the person what is wrong, call `report_issue`, and fix it as [Replace the Microsoft 365 secret](engine.md#replace-the-microsoft-365-secret) says, with its own yes for each change, or install the chart again with the Microsoft 365 values when they were missing. Do not connect Microsoft 365 until both counts are above 0.

Keep the engine app's key file on this machine for now: if the first reads show the secret is wrong, it is rebuilt from that file. It is deleted once Polar Sky has read files through the engine.

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

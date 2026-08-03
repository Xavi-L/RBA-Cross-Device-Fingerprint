export default function Home() {
  return (
    <main className="shell">
      <section className="card" aria-labelledby="page-title">
        <div className="eyebrow">HYBRIDGUARD · WEB 67</div>
        <h1 id="page-title">Available-browser feature probe</h1>
        <p>
          This endpoint is used by the HybridGuard Android compatibility
          collector. A valid one-time collection ticket is required.
        </p>
        <div className="notice" role="status">
          Waiting for a secure launch from the Android app.
        </div>
        <p className="fine-print">
          The probe reads browser-exposed environment signals only. It does not
          request camera, microphone, or location access.
        </p>
      </section>
    </main>
  );
}

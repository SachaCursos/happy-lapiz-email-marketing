export const metadata = {
  title: "Acuerdo de Procesamiento de Datos",
};

export default function DataProcessingAgreementPage() {
  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-gray-100 p-8 md:p-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">
          Acuerdo de Procesamiento de Datos (DPA)
        </h1>
        <p className="text-sm text-gray-400 mb-8">
          Última actualización: 9 de julio de 2026
        </p>

        <div className="space-y-8 text-sm text-gray-700 leading-relaxed">
          <section>
            <p>
              Este Acuerdo de Procesamiento de Datos ("DPA") aplica entre{" "}
              <strong>HotBoat Spa</strong>{" "}
              ("el Procesador", "nosotros") y todo comercio ("el Comercio", "el Responsable")
              que instale nuestra aplicación de email marketing en su tienda Shopify. Al instalar
              la app, el Comercio acepta los términos de este DPA.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">1. Roles</h2>
            <p>
              El Comercio es el <strong>Responsable (Controller)</strong> de los datos
              personales de sus propios clientes. Nosotros actuamos como{" "}
              <strong>Procesador (Processor)</strong>: procesamos esos datos únicamente por
              instrucción del Comercio y para el propósito de prestarle el servicio de email
              marketing (segmentación, campañas, automatizaciones, cupones y reportes).
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              2. Alcance del procesamiento
            </h2>
            <p>
              Procesamos los datos de clientes del Comercio (email, nombre, teléfono, dirección,
              historial de pedidos, consentimiento de marketing) obtenidos vía la API/webhooks de
              Shopify y vía los formularios/píxel de tracking que el Comercio embebe en su
              tienda. El detalle de qué se recolecta y para qué está en nuestra{" "}
              <a href="/legal/privacy" className="text-brand-600 underline">
                Política de Privacidad
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              3. Confidencialidad
            </h2>
            <p>
              Limitamos el acceso a los datos del Comercio al personal que lo necesita para
              operar y dar soporte al servicio, bajo obligaciones de confidencialidad.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              4. Medidas de seguridad
            </h2>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>Encriptación en tránsito (HTTPS/TLS) para toda comunicación con Shopify y con nuestros servidores.</li>
              <li>El token de acceso a la tienda del Comercio se almacena encriptado.</li>
              <li>Base de datos alojada en infraestructura administrada, con acceso restringido.</li>
              <li>Cada instalación queda aislada por tienda (multi-tenant) — un Comercio no puede acceder a los datos de otro.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              5. Subprocesadores
            </h2>
            <p className="mb-2">Usamos los siguientes subprocesadores para operar el servicio:</p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li><strong>Resend</strong> — envío de emails.</li>
              <li><strong>Railway</strong> — hosting de la aplicación y la base de datos.</li>
            </ul>
            <p className="mt-2">
              Notificaremos al Comercio si incorporamos un nuevo subprocesador con acceso a sus
              datos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              6. Solicitudes de titulares de datos
            </h2>
            <p>
              Implementamos los webhooks de cumplimiento que exige Shopify: cuando un cliente
              final pide el borrado de sus datos (
              <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">customers/redact</code>),
              anonimizamos/eliminamos su información automáticamente. Cuando se solicita una
              copia de los datos (
              <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">customers/data_request</code>
              ), generamos automáticamente un export de esa información y se lo enviamos por
              email al dueño del Comercio.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              7. Eliminación de datos al desinstalar
            </h2>
            <p>
              Cuando el Comercio desinstala la app, eliminamos todos sus datos (contactos,
              campañas, automatizaciones, historial de envíos) de forma automática, conforme al
              webhook{" "}
              <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">shop/redact</code> de
              Shopify.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">8. Contacto</h2>
            <p>
              HotBoat Spa
              <br />
              tomasdamjanic@gmail.com
            </p>
          </section>

          <section className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-400">
              Este documento es una plantilla de referencia y no reemplaza asesoría legal.
              Revisalo con un abogado antes de publicarlo como acuerdo vinculante con
              comercios reales, especialmente en lo referido a responsabilidad, jurisdicción y
              cumplimiento normativo local (ej. Ley 19.628 en Chile, GDPR si aplica a clientes en
              la UE).
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

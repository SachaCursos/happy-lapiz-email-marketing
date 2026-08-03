export const metadata = {
  title: "Términos de Servicio",
};

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-gray-100 p-8 md:p-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Términos de Servicio</h1>
        <p className="text-sm text-gray-400 mb-8">
          Última actualización: 3 de agosto de 2026
        </p>

        <div className="space-y-8 text-sm text-gray-700 leading-relaxed">
          <section>
            <p>
              Estos Términos de Servicio ("Términos") rigen el uso de nuestra aplicación de email
              marketing para tiendas Shopify (la "App"), operada por <strong>HotBoat Spa</strong>{" "}
              ("nosotros", "el Proveedor"). Al instalar o usar la App, el comercio que la instala
              ("el Comercio", "vos") acepta estos Términos.
            </p>
            <p className="mt-3">
              El tratamiento de datos personales de los clientes del Comercio se rige además por
              nuestra{" "}
              <a href="/legal/privacy" className="text-brand-600 underline">
                Política de Privacidad
              </a>{" "}
              y nuestro{" "}
              <a href="/legal/dpa" className="text-brand-600 underline">
                Acuerdo de Procesamiento de Datos
              </a>
              , que forman parte integral de estos Términos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">1. El servicio</h2>
            <p>
              La App permite al Comercio segmentar sus contactos, enviar campañas y
              automatizaciones de email, gestionar cupones y formularios de suscripción, y ver
              reportes de rendimiento de sus propios envíos. La App se instala desde el Shopify
              App Store y requiere los permisos (scopes) que se muestran en la pantalla de
              instalación para funcionar.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              2. Cuenta y responsabilidad del Comercio
            </h2>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>
                El Comercio es responsable de mantener la confidencialidad de las credenciales de
                acceso a su cuenta y de toda actividad que ocurra bajo ella.
              </li>
              <li>
                El Comercio garantiza tener el consentimiento legal necesario de sus propios
                clientes para enviarles comunicaciones de marketing a través de la App, conforme a
                la normativa aplicable (incluyendo, sin limitarse a, la Ley 19.628 en Chile, y
                GDPR/CAN-SPAM cuando corresponda).
              </li>
              <li>
                El Comercio es responsable del contenido de las campañas, automatizaciones y
                formularios que crea con la App.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">3. Uso aceptable</h2>
            <p className="mb-2">El Comercio se compromete a no usar la App para:</p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>Enviar spam o comunicaciones a contactos que no dieron su consentimiento.</li>
              <li>Enviar contenido ilegal, fraudulento, difamatorio o que infrinja derechos de terceros.</li>
              <li>Intentar acceder a datos de otro Comercio o vulnerar el aislamiento entre tiendas.</li>
              <li>Interferir con la operación normal de la App o de la infraestructura que la sostiene.</li>
            </ul>
            <p className="mt-2">
              Nos reservamos el derecho de suspender el acceso de un Comercio que incumpla este
              punto.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">4. Precios y facturación</h2>
            <p>
              El plan y las tarifas vigentes se muestran en la ficha de la App dentro del Shopify
              App Store al momento de instalar o actualizar el plan. La facturación, cuando
              aplique, se gestiona a través del sistema de facturación de Shopify (Shopify
              Billing) conforme a sus propios términos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              5. Disponibilidad del servicio
            </h2>
            <p>
              Hacemos esfuerzos razonables para mantener la App disponible, pero no garantizamos
              un funcionamiento ininterrumpido o libre de errores. Podemos realizar mantenimiento,
              actualizaciones o cambios a la App en cualquier momento.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              6. Propiedad intelectual
            </h2>
            <p>
              La App, su código, diseño y marca son propiedad de HotBoat Spa. El Comercio conserva
              todos los derechos sobre su propio contenido (plantillas, textos, imágenes que sube)
              y sobre los datos de sus clientes.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              7. Limitación de responsabilidad
            </h2>
            <p>
              En la medida permitida por la ley, no seremos responsables por daños indirectos,
              incidentales o consecuentes derivados del uso de la App, incluyendo pérdida de
              ingresos, datos o clientes, más allá de lo pagado por el Comercio por el servicio en
              los últimos 12 meses.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              8. Suspensión y término
            </h2>
            <p>
              El Comercio puede dejar de usar la App en cualquier momento desinstalándola desde su
              admin de Shopify. Al desinstalarla, eliminamos los datos del Comercio conforme al
              webhook{" "}
              <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">shop/redact</code> de
              Shopify — ver el detalle en nuestra{" "}
              <a href="/legal/privacy" className="text-brand-600 underline">
                Política de Privacidad
              </a>
              . Podemos suspender o terminar el acceso de un Comercio que incumpla estos Términos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">9. Cambios a estos Términos</h2>
            <p>
              Podemos actualizar estos Términos ocasionalmente. Publicaremos cualquier cambio en
              esta misma página con su fecha de actualización. El uso continuado de la App tras un
              cambio implica la aceptación de los nuevos Términos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">10. Ley aplicable</h2>
            <p>
              Estos Términos se rigen por las leyes de Chile. Cualquier disputa se someterá a los
              tribunales competentes de Chile, salvo que la normativa aplicable exija lo
              contrario.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">11. Contacto</h2>
            <p>
              HotBoat Spa
              <br />
              Laguna Rivera 1, Pucón, Chile
              <br />
              tomasdamjanic@gmail.com
            </p>
          </section>

          <section className="border-t border-gray-100 pt-6">
            <p className="text-xs text-gray-400">
              Este documento es una plantilla de referencia y no reemplaza asesoría legal.
              Revisalo con un abogado antes de publicarlo como términos vinculantes con comercios
              reales, especialmente en lo referido a limitación de responsabilidad, facturación y
              jurisdicción.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

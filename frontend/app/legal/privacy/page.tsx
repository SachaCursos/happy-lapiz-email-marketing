export const metadata = {
  title: "Política de Privacidad",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-gray-50 px-4 py-12">
      <div className="max-w-3xl mx-auto bg-white rounded-2xl shadow-sm border border-gray-100 p-8 md:p-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Política de Privacidad</h1>
        <p className="text-sm text-gray-400 mb-8">
          Última actualización: 9 de julio de 2026
        </p>

        <div className="space-y-8 text-sm text-gray-700 leading-relaxed">
          <section>
            <p>
              Esta Política de Privacidad describe cómo{" "}
              <strong>HotBoat Spa</strong>{" "}
              ("nosotros", "la App") recolecta, usa y protege los datos personales al operar
              nuestra aplicación de email marketing para tiendas Shopify.
            </p>
            <p className="mt-3">
              La App funciona como <strong>procesador de datos</strong> en nombre de cada
              comercio (merchant) que la instala. El comercio es el{" "}
              <strong>responsable (controlador)</strong> de los datos de sus propios clientes;
              nosotros procesamos esos datos únicamente para prestarle el servicio de email
              marketing al comercio.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              1. Qué datos recolectamos
            </h2>
            <p className="mb-2">Según de dónde provengan, procesamos:</p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>
                <strong>Desde la API de Shopify, al instalar la app</strong> (Customers API):
                email, nombre, teléfono, dirección, historial de pedidos y estado de
                consentimiento de marketing del cliente.
              </li>
              <li>
                <strong>Desde webhooks de Shopify</strong>: eventos de carrito abandonado,
                pedidos, envíos y cancelaciones — incluyen email, nombre, dirección de envío y
                los productos del pedido.
              </li>
              <li>
                <strong>Desde formularios/pop-ups embebidos en la tienda</strong>: email,
                nombre, teléfono y campos personalizados que el visitante completa
                voluntariamente al suscribirse.
              </li>
              <li>
                <strong>Desde el píxel de tracking embebido en la tienda</strong>: productos
                vistos y actividad de navegación, asociados al email cuando el visitante ya se
                identificó (por ejemplo, tras suscribirse).
              </li>
              <li>
                <strong>Datos de la tienda</strong>: dominio, email del dueño, plan y moneda,
                obtenidos al momento de instalar la app.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              2. Para qué usamos estos datos
            </h2>
            <p>Usamos los datos exclusivamente para prestarle el servicio de email marketing al comercio que instaló la app:</p>
            <ul className="list-disc pl-5 space-y-1.5 mt-2">
              <li>Segmentar contactos y personalizar campañas de email.</li>
              <li>
                Enviar automatizaciones activadas por eventos de la tienda (recuperación de
                carrito abandonado, confirmación/seguimiento de pedido, entrega de cupones,
                etc.).
              </li>
              <li>Mostrarle al comercio reportes y estadísticas de sus propias campañas.</li>
            </ul>
            <p className="mt-2">
              No usamos estos datos para ningún otro fin, y no los vendemos ni los compartimos
              con terceros para publicidad.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              3. Con quién compartimos datos (subprocesadores)
            </h2>
            <p className="mb-2">
              Usamos los siguientes proveedores para operar el servicio, cada uno procesando
              datos únicamente en la medida necesaria para su función:
            </p>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>
                <strong>Resend</strong> — envío de los emails de campañas y automatizaciones.
              </li>
              <li>
                <strong>Railway</strong> — hosting de la aplicación y de la base de datos.
              </li>
              <li>
                <strong>Shopify</strong> — origen de los datos de clientes/pedidos/productos vía
                su API.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">4. Seguridad</h2>
            <ul className="list-disc pl-5 space-y-1.5">
              <li>Toda la comunicación con la API de Shopify y con nuestros servidores viaja encriptada (HTTPS/TLS).</li>
              <li>El token de acceso de cada tienda se guarda encriptado en nuestra base de datos.</li>
              <li>El acceso a la base de datos está restringido y alojado en infraestructura administrada con encriptación en reposo.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              5. Retención y eliminación de datos
            </h2>
            <p>
              Conservamos los datos de un comercio mientras la app esté instalada y prestando
              servicio. Cuando un comercio desinstala la app, eliminamos todos sus datos
              (contactos, campañas, automatizaciones, etc.) automáticamente, conforme al webhook
              de cumplimiento <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">shop/redact</code>{" "}
              de Shopify.
            </p>
            <p className="mt-2">
              Cuando Shopify nos notifica que un cliente final pidió el borrado de sus datos
              (<code className="text-xs bg-gray-100 px-1 py-0.5 rounded">customers/redact</code>),
              anonimizamos o eliminamos su información personal de nuestra base de datos.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">
              6. Tus derechos / cómo darte de baja
            </h2>
            <p>
              Todo email de marketing que enviamos incluye un enlace de cancelación de
              suscripción. Si querés ejercer otros derechos sobre tus datos (acceso,
              rectificación, eliminación), podés contactar directamente al comercio con el que
              tenés relación, o escribirnos a{" "}
              <strong>tomasdamjanic@gmail.com</strong>.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">7. Menores de edad</h2>
            <p>No recolectamos intencionalmente datos de menores de edad.</p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">8. Cambios a esta política</h2>
            <p>
              Podemos actualizar esta política ocasionalmente. Publicaremos cualquier cambio en
              esta misma página con su fecha de actualización.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900 mb-2">9. Contacto</h2>
            <p>
              HotBoat Spa
              <br />
              Laguna Rivera 1, Pucón, Chile
              <br />
              tomasdamjanic@gmail.com
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

;; Provision the QA administrator non-interactively (the app's own
;; `bb create-admin` needs a console). Run from the app repo root so the default
;; `.secrets/auth-secret` resolves:
;;
;;   ALMA_QA_ADMIN_USERNAME=qa.admin ALMA_QA_ADMIN_DISPLAY_NAME="QA Admin" \
;;   ALMA_DB_PASSWORD_FILE=... ALMA_DB_PORT=... clojure -Srepro -M <this file>
;;
;; Prints the one-time temporary password as the last stdout line. Fails (exit
;; 1) when any account already exists - bootstrap only works on a fresh DB.
(require '[alma-spei.api.auth.service :as service]
         '[alma-spei.api.config :as config]
         '[alma-spei.api.db.core :as db])

(try
  (let [result (service/bootstrap!
                (db/datasource (:database (config/load-config)))
                {:username (System/getenv "ALMA_QA_ADMIN_USERNAME")
                 :display-name (System/getenv "ALMA_QA_ADMIN_DISPLAY_NAME")})]
    (println (:temporary-password result))
    (flush)
    (System/exit 0))
  (catch Exception e
    (binding [*out* *err*] (println "QA admin provisioning failed:" (ex-message e)))
    (System/exit 1)))

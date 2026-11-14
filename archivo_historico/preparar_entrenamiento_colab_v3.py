"""Paquete autocontenido para entrenar v3 en el entorno de Colab."""
from pathlib import Path
import zipfile
import json
import hashlib

BASE=Path(__file__).resolve().parent
codigo='''# ENTRENAMIENTO COMPLETO V3 EN COLAB (puede tardar varios minutos)
# Reproduccion: estos test ya se evaluaron localmente; no son test nuevos.
from google.colab import files
from pathlib import Path
import zipfile, sys, subprocess, json, hashlib, datetime
print('Selecciona Pisciber_Entrenamiento_v3.zip')
subidos_v3=files.upload()
nombre_v3=next(n for n in subidos_v3 if n.endswith('.zip'))
raiz_v3=Path('/content')/('pisciber_entrenamiento_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
raiz_v3.mkdir()
z_v3=zipfile.ZipFile(nombre_v3)
assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z_v3.namelist())
manifiesto_v3=json.loads(z_v3.read('manifest.json'))
assert all(hashlib.sha256(z_v3.read(n)).hexdigest()==h for n,h in manifiesto_v3.items())
z_v3.extractall(raiz_v3)
z_v3.close()
print('Paquete verificado. Pruebas de historia temporal y objetivos...')
subprocess.run([sys.executable,'-m','unittest','test_mejora','-v'],cwd=raiz_v3,check=True)
print('Iniciando 27 ajustes de validacion cruzada, calibracion y prueba...')
subprocess.run([sys.executable,'-u','mejorar_predicciones.py'],cwd=raiz_v3,check=True)
print('Verificando modelos y predicciones guardadas...')
subprocess.run([sys.executable,'-u','revisar_mejora.py'],cwd=raiz_v3,check=True)
exec(compile((raiz_v3/'mostrar_resultados_v3.py').read_text(),str(raiz_v3/'mostrar_resultados_v3.py'),'exec'),{'__file__':str(raiz_v3/'mostrar_resultados_v3.py')})
files.download(str(raiz_v3/'Resultados_Pisciber_v3.zip'))
print('ENTRENAMIENTO COMPLETO TERMINADO EN COLAB')
'''
if __name__=='__main__':
    nombres=['mejorar_predicciones.py','experimento_mortalidad.py','entrenar_mortalidad.py','revisar_mejora.py',
        'mostrar_resultados_v3.py','test_mejora.py','requirements-ml.txt','SUPUESTOS_SIMULACION.md']
    nombres += ['experimento_v3/'+n for n in ['datos.csv','eventos.csv','metadatos.json','corridas.csv']]
    with zipfile.ZipFile(BASE/'Pisciber_Entrenamiento_v3.zip','w',zipfile.ZIP_DEFLATED) as z:
        hashes={}
        for n in nombres:
            z.write(BASE/n,n)
            hashes[n]=hashlib.sha256((BASE/n).read_bytes()).hexdigest()
        z.writestr('manifest.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(BASE/'Pisciber_Entrenamiento_v3.zip') as z: assert z.testzip() is None
    compile(codigo,'<Colab v3>','exec')
    nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3'}},'cells':[
        {'cell_type':'markdown','metadata':{},'source':['# Pisciber: entrenamiento completo v3\n','Reproduce el protocolo para horizontes de 1, 6 y 12 horas. Sube el paquete de entrenamiento, no el ZIP de resultados.']},
        {'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':codigo.splitlines(True)}]}
    (BASE/'Pisciber_Entrenamiento_v3.ipynb').write_text(json.dumps(nb,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Paquete verificado:',(BASE/'Pisciber_Entrenamiento_v3.zip').stat().st_size,'bytes')
